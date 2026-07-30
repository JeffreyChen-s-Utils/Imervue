"""Recycle Bin dialog for the soft-delete undo stack.

The viewer's ``undo_stack`` holds ``{"mode": "delete", ...}`` actions whose
files are kept on disk until ``commit_pending_deletions`` runs at app
shutdown. Until then a deletion is reversible. This dialog surfaces every
*pending* deletion so users can:

* See exactly what will be unlinked at shutdown.
* Restore individual items (puts the path back at its saved index and
  reloads the thumbnail).
* Permanently delete individual items right now — the entry leaves the undo
  stack immediately and the disk work runs on a background worker in
  grouped batches (see :mod:`Imervue.system.trash_ops`).

Design notes:

* The dialog reads the live ``undo_stack`` — it doesn't snapshot, so a
  restore in deep-zoom updates the dialog without surprises if you keep
  it open.
* All mutations go through small helpers (``restore_item`` / ``purge_item``)
  that keep the undo-stack invariants intact: an action's ``deleted_paths``
  and ``indices`` arrays stay aligned, an action with no paths left is
  marked ``restored=True`` so ``commit_pending_deletions`` skips it.
* The list view is read-only; users act on the toolbar / context-menu
  buttons, not by editing rows.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.worker_host import WorkerHostMixin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.recycle_bin")


# ---------------------------------------------------------------------------
# Pure helpers — no Qt, no I/O. Tested directly.
# ---------------------------------------------------------------------------


# Soft-delete action modes the Recycle Bin surfaces. ``delete`` is an image
# removed from the viewer list (kept on disk, restored back into the list);
# ``delete_external`` is a folder / non-list file deleted from the file tree
# (kept on disk, hidden from the tree, sent to the OS trash only at shutdown).
_PENDING_MODES = ("delete", "delete_external")


def list_pending_entries(undo_stack: list[dict]) -> list[dict]:
    """Flatten an undo-stack into one entry per pending deletion.

    Each entry exposes the indices we need to mutate the original action
    in-place: ``action_idx`` is the index into ``undo_stack``, ``path_idx``
    is the position inside that action's ``deleted_paths`` list. ``kind`` is
    ``"image"`` for viewer-list deletions or ``"external"`` for folder / file
    tree deletions, so restore can pick the right recovery.
    """
    entries: list[dict] = []
    for action_idx, action in enumerate(undo_stack):
        mode = action.get("mode")
        if mode not in _PENDING_MODES or action.get("restored"):
            continue
        kind = "external" if mode == "delete_external" else "image"
        paths = action.get("deleted_paths", [])
        indices = action.get("indices", [])
        for path_idx, path in enumerate(paths):
            entries.append({
                "action_idx": action_idx,
                "path_idx": path_idx,
                "path": path,
                "kind": kind,
                "original_index": indices[path_idx] if path_idx < len(indices) else 0,
            })
    return entries


def pending_external_paths(undo_stack: list[dict]) -> set[str]:
    """Return the folder / file-tree paths still pending soft-deletion.

    These are kept on disk but hidden from the file tree until the user
    restores them or the app commits the deletions at shutdown.
    """
    out: set[str] = set()
    for action in undo_stack:
        if action.get("mode") == "delete_external" and not action.get("restored"):
            out.update(action.get("deleted_paths", []))
    return out


def remove_path_from_action(action: dict, path_idx: int) -> tuple[str, int] | None:
    """Pop the ``path_idx``-th deletion from ``action``.

    Returns ``(path, original_index)`` so the caller can restore it, or
    ``None`` if the index is out of range. Marks the action ``restored``
    when its last path is removed so the commit hook skips it.
    """
    paths = action.get("deleted_paths", [])
    indices = action.get("indices", [])
    if path_idx < 0 or path_idx >= len(paths):
        return None
    path = paths.pop(path_idx)
    original_index = indices.pop(path_idx) if path_idx < len(indices) else 0
    if not paths:
        action["restored"] = True
    return path, original_index


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class RecycleBinDialog(WorkerHostMixin, QDialog):
    """Lists pending soft-deletions with per-item restore / purge."""

    def __init__(self, viewer: GPUImageView, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        # Background purge worker, or None when idle (see WorkerHostMixin).
        self._worker = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("recycle_bin_title", "Recycle Bin"))
        self.setModal(True)
        self.resize(680, 420)

        layout = QVBoxLayout(self)
        self._tree = self._build_tree()
        layout.addWidget(self._tree)
        layout.addLayout(self._build_buttons())

        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_tree(self) -> QTreeWidget:
        lang = language_wrapper.language_word_dict
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderLabels([
            lang.get("recycle_bin_col_name", "Name"),
            lang.get("recycle_bin_col_path", "Path"),
        ])
        tree.setRootIsDecorated(False)
        tree.setUniformRowHeights(True)
        tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        tree.setSortingEnabled(True)
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        return tree

    def _build_buttons(self) -> QHBoxLayout:
        lang = language_wrapper.language_word_dict
        row = QHBoxLayout()

        btn_restore = QPushButton(lang.get("recycle_bin_restore", "Restore"))
        btn_restore.clicked.connect(self._restore_selected)
        row.addWidget(btn_restore)

        btn_purge = QPushButton(lang.get("recycle_bin_purge", "Delete Forever"))
        btn_purge.clicked.connect(self._purge_selected)
        row.addWidget(btn_purge)

        row.addStretch(1)

        btn_close = QPushButton(lang.get("close", "Close"))
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_close)
        return row

    # ------------------------------------------------------------------
    # Refresh / population
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._tree.clear()
        for entry in list_pending_entries(self._viewer.undo_stack):
            path = entry["path"]
            name = Path(path).name if path else ""
            item = QTreeWidgetItem([name, path])
            item.setData(0, Qt.ItemDataRole.UserRole, entry)
            self._tree.addTopLevelItem(item)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_entries(self) -> list[dict]:
        """Return the selected rows' entry dicts (live, not snapshots)."""
        items = self._tree.selectedItems()
        return [it.data(0, Qt.ItemDataRole.UserRole) for it in items]

    def _restore_selected(self) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        # Sort entries from highest path_idx down so popping doesn't shift
        # earlier ones. Group by action so action_idx stays stable too.
        for entry in sorted(
            entries,
            key=lambda e: (e["action_idx"], e["path_idx"]),
            reverse=True,
        ):
            self._restore_one(entry)
        self.refresh()

    def _restore_one(self, entry: dict) -> None:
        viewer = self._viewer
        action_idx = entry["action_idx"]
        if action_idx >= len(viewer.undo_stack):
            return
        action = viewer.undo_stack[action_idx]
        result = remove_path_from_action(action, entry["path_idx"])
        if result is None:
            return
        path, original_index = result
        if entry.get("kind") == "external":
            self._restore_external()
            return
        images = viewer.model.images
        insert_at = max(0, min(original_index, len(images)))
        images.insert(insert_at, path)
        self._reload_thumbnail(path)

    def _restore_external(self) -> None:
        """Un-hide restored folders / files by re-syncing the file tree."""
        tree = getattr(self._main_window(), "tree", None)
        refresh = getattr(tree, "refresh_pending_hidden", None)
        if callable(refresh):
            refresh()

    def _reload_thumbnail(self, path: str) -> None:
        try:
            from Imervue.gpu_image_view.images.load_thumbnail_worker import (
                LoadThumbnailWorker,
            )
        except ImportError:
            logger.debug("LoadThumbnailWorker unavailable — skipping reload")
            return
        viewer = self._viewer
        worker = LoadThumbnailWorker(
            path, viewer.thumbnail_size, viewer._load_generation,
        )
        worker.signals.finished.connect(viewer.add_thumbnail)
        viewer.thread_pool.start(worker)

    def _purge_selected(self) -> None:
        """Detach the selected entries, then delete them on a worker thread.

        The undo stack and the list are updated immediately so the dialog
        stays live; the disk work is batched and backgrounded because one
        ``send2trash`` shell call costs ~0.27 s, which froze the dialog for
        minutes when purging a few hundred entries one at a time.
        """
        entries = self._selected_entries()
        if not entries:
            return
        if not self._confirm_purge(len(entries)):
            return
        unlink_paths: list[str] = []
        trash_paths: list[str] = []
        for entry in sorted(
            entries,
            key=lambda e: (e["action_idx"], e["path_idx"]),
            reverse=True,
        ):
            path = self._detach_entry(entry)
            if not path:
                continue
            group = trash_paths if entry.get("kind") == "external" else unlink_paths
            group.append(path)
        if trash_paths:
            self._restore_external()  # re-sync the tree's hidden rows once
        self.refresh()
        self._purge_in_background(unlink_paths, trash_paths)

    def _confirm_purge(self, count: int) -> bool:
        lang = language_wrapper.language_word_dict
        title = lang.get("recycle_bin_purge", "Delete Forever")
        message = lang.get(
            "recycle_bin_purge_confirm",
            "Permanently delete {count} item(s)? This cannot be undone.",
        ).format(count=count)
        result = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _detach_entry(self, entry: dict) -> str | None:
        """Pop *entry*'s path out of the undo stack; returns that path."""
        viewer = self._viewer
        action_idx = entry["action_idx"]
        if action_idx >= len(viewer.undo_stack):
            return None
        result = remove_path_from_action(
            viewer.undo_stack[action_idx], entry["path_idx"])
        return result[0] if result is not None else None

    def _purge_in_background(self, unlink_paths: list[str],
                             trash_paths: list[str]) -> None:
        """Run the actual deletions on a worker so the dialog stays responsive."""
        if not unlink_paths and not trash_paths:
            return
        from Imervue.system.trash_ops import FilePurgeWorker
        worker = FilePurgeWorker(unlink_paths, trash_paths, parent=self)
        worker.progress.connect(self._on_purge_progress)
        worker.finished_with.connect(self._on_purge_finished)
        self._worker = worker
        worker.start()

    def _main_window(self):
        return getattr(self._viewer, "main_window", None)

    def _on_purge_progress(self, done: int, total: int) -> None:
        window = self._main_window()
        if hasattr(window, "show_progress"):
            window.show_progress(done, total)

    def _on_purge_finished(self, _removed: list, failed: list) -> None:
        self._worker = None
        if not failed:
            return
        window = self._main_window()
        if hasattr(window, "toast"):
            lang = language_wrapper.language_word_dict
            window.toast.warning(
                lang.get(
                    "recycle_bin_purge_failed",
                    "Couldn't delete {count} item(s)",
                ).format(count=len(failed)),
            )
        logger.warning("Recycle Bin purge failed on %d path(s)", len(failed))

    def accept(self):  # noqa: N802 - Qt API
        # Close must join a running purge: this dialog is a temporary
        # (``RecycleBinDialog(...).exec()``) whose QThread child would
        # otherwise be destroyed mid-run.
        self._stop_worker()
        super().accept()


def open_recycle_bin_dialog(viewer: GPUImageView, parent=None) -> None:
    dlg = RecycleBinDialog(viewer, parent=parent)
    dlg.exec()
