"""Recycle Bin dialog for the soft-delete undo stack.

The viewer's ``undo_stack`` holds ``{"mode": "delete", ...}`` actions whose
files are kept on disk until ``commit_pending_deletions`` runs at app
shutdown. Until then a deletion is reversible. This dialog surfaces every
*pending* deletion so users can:

* See exactly what will be unlinked at shutdown.
* Restore individual items (puts the path back at its saved index and
  reloads the thumbnail).
* Permanently delete individual items right now (unlinks immediately so
  the action is gone from the undo stack).

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

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.recycle_bin")


# ---------------------------------------------------------------------------
# Pure helpers — no Qt, no I/O. Tested directly.
# ---------------------------------------------------------------------------


def list_pending_entries(undo_stack: list[dict]) -> list[dict]:
    """Flatten an undo-stack into one entry per pending deletion.

    Each entry exposes the indices we need to mutate the original action
    in-place: ``action_idx`` is the index into ``undo_stack``, ``path_idx``
    is the position inside that action's ``deleted_paths`` list.
    """
    entries: list[dict] = []
    for action_idx, action in enumerate(undo_stack):
        if action.get("mode") != "delete" or action.get("restored"):
            continue
        paths = action.get("deleted_paths", [])
        indices = action.get("indices", [])
        for path_idx, path in enumerate(paths):
            entries.append({
                "action_idx": action_idx,
                "path_idx": path_idx,
                "path": path,
                "original_index": indices[path_idx] if path_idx < len(indices) else 0,
            })
    return entries


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


class RecycleBinDialog(QDialog):
    """Lists pending soft-deletions with per-item restore / purge."""

    def __init__(self, viewer: GPUImageView, parent=None):
        super().__init__(parent)
        self._viewer = viewer
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
        images = viewer.model.images
        insert_at = max(0, min(original_index, len(images)))
        images.insert(insert_at, path)
        self._reload_thumbnail(path)

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
        entries = self._selected_entries()
        if not entries:
            return
        if not self._confirm_purge(len(entries)):
            return
        for entry in sorted(
            entries,
            key=lambda e: (e["action_idx"], e["path_idx"]),
            reverse=True,
        ):
            self._purge_one(entry)
        self.refresh()

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

    def _purge_one(self, entry: dict) -> None:
        viewer = self._viewer
        action_idx = entry["action_idx"]
        if action_idx >= len(viewer.undo_stack):
            return
        action = viewer.undo_stack[action_idx]
        result = remove_path_from_action(action, entry["path_idx"])
        if result is None:
            return
        path, _ = result
        try:
            if path and Path(path).exists():
                Path(path).unlink()
        except OSError as exc:
            logger.error("Failed to purge %s: %s", path, exc)


def open_recycle_bin_dialog(viewer: GPUImageView, parent=None) -> None:
    dlg = RecycleBinDialog(viewer, parent=parent)
    dlg.exec()
