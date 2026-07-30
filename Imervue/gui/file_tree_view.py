"""File-tree view for the main window.

The QTreeView subclass with keyboard shortcuts and right-click menu, plus the
duplicate-name helper. Extracted from ``Imervue_main_window``; re-exported
there for backwards compatibility.
"""
import os
import subprocess  # nosec B404  # NOSONAR - static arg lists for trusted OS file managers
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QApplication, QTreeView, QFileSystemModel, QMenu,
)

from Imervue.gui.folder_thumbnail_model import clamp_icon_size

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib


def _next_duplicate_name(source: Path) -> Path:
    """Pick a sibling path for ``source`` that does not exist yet, in
    the form ``stem (copy).ext``, ``stem (copy 2).ext``, …"""
    parent = source.parent
    stem = source.stem
    suffix = source.suffix
    candidate = parent / f"{stem} (copy){suffix}"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = parent / f"{stem} (copy {n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def _partition_delete_batch(
    paths: Iterable[str], images: Iterable[str],
) -> tuple[list[str], list[str], list[str]]:
    """Split a delete batch into (viewer-list files, folders, loose files).

    Viewer-list files soft-delete in memory (no disk I/O until shutdown),
    folders soft-delete through the app Recycle Bin, and loose files are the
    only group that needs OS-trash calls right away.
    """
    image_set = set(images)
    in_list: list[str] = []
    folders: list[str] = []
    loose: list[str] = []
    for path in paths:
        if Path(path).is_dir():
            folders.append(path)
        elif path in image_set:
            in_list.append(path)
        else:
            loose.append(path)
    return in_list, folders, loose


def _dedupe_paths(paths: Iterable[str]) -> list[str]:
    """Order-preserving de-duplication of paths, dropping empty strings.

    The selection model yields one index per selected row but a path can
    repeat (e.g. the same file reachable through an expanded + collapsed
    branch); the batch ops need each path exactly once.
    """
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out


class _FileTreeView(QTreeView):
    """QTreeView with Delete key and right-click context menu."""

    _ZOOM_STEP = 8  # px per Ctrl+wheel notch when resizing folder thumbnails
    # Raw-QFileSystemModel fallback columns, used only when the model isn't
    # the FileTreeSortProxy (tests, plain models). "created" has no native
    # column, so the fallback approximates it with the modified column.
    _TREE_SORT_COLUMNS = {
        "name": 0,
        "size": 1,
        "modified": 3,
        "created": 3,
    }
    _TREE_SORT_LANG_KEYS = {
        "name": "sort_by_name",
        "size": "sort_by_size",
        "modified": "sort_by_modified",
        "created": "sort_by_created",
    }

    def __init__(self, main_window: "ImervueMainWindow"):
        super().__init__()
        self._main_window = main_window
        self._search_text = ""
        # Folders pending soft-deletion are kept on disk but hidden from the
        # tree until restored or committed at shutdown; track what we hid so a
        # restore can un-hide exactly those rows.
        self._hidden_paths: set[str] = set()
        # In-flight background trash workers — referenced here so they are
        # not garbage-collected mid-run; each self-evicts on finish.
        self._trash_workers: set = set()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        # Ctrl/Shift multi-select so batch delete / copy-paths can act on
        # several files at once. A plain single click still selects and
        # opens one file via the main window's ``clicked`` handler.
        self.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)

    def setModel(self, model) -> None:
        super().setModel(model)
        # Re-apply the pending-delete hidden rows whenever a directory finishes
        # (re)loading, so navigating away and back keeps deleted folders hidden.
        loaded = getattr(model, "directoryLoaded", None)
        if loaded is not None:
            loaded.connect(lambda _path: self.refresh_pending_hidden())
            loaded.connect(lambda _path: self.apply_search_filter())
        self._apply_tree_sort_from_settings()

    def refresh_pending_hidden(self) -> None:
        """Hide rows for folders pending soft-deletion; un-hide the rest."""
        from Imervue.gui.recycle_bin_dialog import pending_external_paths
        viewer = getattr(self._main_window, "viewer", None)
        pending = pending_external_paths(getattr(viewer, "undo_stack", None) or [])
        model = self.model()
        if model is None:
            return
        for path in self._hidden_paths - pending:
            self._set_row_hidden(model, path, hidden=False)
        for path in pending:
            self._set_row_hidden(model, path, hidden=True)
        self._hidden_paths = set(pending)

    def _set_row_hidden(self, model, path: str, *, hidden: bool) -> None:
        index = model.index(path)
        if index.isValid():
            self.setRowHidden(index.row(), index.parent(), hidden)

    def set_thumbnail_size(self, px: int) -> None:
        """Resize the folder preview icons (view + model) and remember it."""
        size = clamp_icon_size(px)
        self.setIconSize(QSize(size, size))
        model = self.model()
        if hasattr(model, "set_icon_size"):
            model.set_icon_size(size)
        from Imervue.user_settings.user_setting_dict import (
            schedule_save,
            user_setting_dict,
        )
        user_setting_dict["tree_thumbnail_size"] = size
        schedule_save()
        self.viewport().update()

    def wheelEvent(self, event):
        # Ctrl+wheel dynamically grows / shrinks the folder thumbnails; a plain
        # wheel scrolls the tree as usual.
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step = self._ZOOM_STEP if event.angleDelta().y() > 0 else -self._ZOOM_STEP
            self.set_thumbnail_size(self.iconSize().width() + step)
            event.accept()
            return
        super().wheelEvent(event)

    def _selected_paths(self) -> list[str]:
        """Unique filesystem paths for every selected row (column 0)."""
        model: QFileSystemModel = self.model()
        return _dedupe_paths(
            model.filePath(index) for index in self.selectionModel().selectedRows()
        )

    # ---------- Keyboard shortcuts ----------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Delete:
            self._delete_selected()
            return
        if key == Qt.Key.Key_F5:
            self._refresh_tree()
            return
        if key == Qt.Key.Key_F2:
            self._rename_selected()
            return
        super().keyPressEvent(event)

    def _rename_selected(self) -> None:
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        model: QFileSystemModel = self.model()
        path = model.filePath(indexes[0])
        if path:
            self._rename_path(path)

    def _refresh_tree(self) -> None:
        """Force QFileSystemModel to re-scan the current root.

        Useful when external tools have changed the folder contents and
        Qt's native watcher hasn't picked it up yet.
        """
        model: QFileSystemModel = self.model()
        root = self.rootIndex()
        if not root.isValid():
            return
        path = model.filePath(root)
        if path:
            # Re-attempt any folder whose preview is currently missing (it may
            # have just gained an image, or recovered from a mid-delete read).
            clear_missing = getattr(model, "clear_missing_previews", None)
            if callable(clear_missing):
                clear_missing()
            # setRootPath() re-stats the directory even if the value is the same
            model.setRootPath("")
            model.setRootPath(path)
            self.setRootIndex(model.index(path))
            self.apply_search_filter()

    def _delete_selected(self):
        self._delete_paths(self._selected_paths())

    # ---------- Right-click menu ----------

    def _show_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            self._show_tree_context_menu(pos)
            return
        model: QFileSystemModel = self.model()
        path = model.filePath(index)
        if not path:
            return
        # When the user right-clicks a row that is part of a multi-selection,
        # offer the batch menu; otherwise fall back to the full single-item
        # menu (rename / duplicate / new folder etc. only make sense for one).
        selected = self._selected_paths()
        if len(selected) > 1 and path in selected:
            self._show_multi_context_menu(selected, pos)
        else:
            self._show_single_context_menu(path, pos)

    def _show_tree_context_menu(self, pos) -> None:
        """Context menu for blank tree space: sort + refresh."""
        lang = language_wrapper.language_word_dict
        menu = QMenu(self)
        self._add_sort_menu(menu)
        menu.addSeparator()
        action_refresh = menu.addAction(lang.get("tree_refresh", "Refresh"))
        action_refresh.triggered.connect(self._refresh_tree)
        menu.exec(self.viewport().mapToGlobal(pos))

    def _show_multi_context_menu(self, paths: list[str], pos) -> None:
        """Context menu for a multi-row selection: reveal, copy paths, delete."""
        lang = language_wrapper.language_word_dict
        menu = QMenu(self)
        self._add_sort_menu(menu)
        menu.addSeparator()

        action_explorer = menu.addAction(
            lang.get("tree_open_in_explorer", "Open in Explorer")
        )
        action_explorer.triggered.connect(lambda: self._open_in_explorer(paths[0]))

        action_copy = menu.addAction(lang.get("tree_copy_paths", "Copy Paths"))
        action_copy.triggered.connect(
            lambda: QApplication.clipboard().setText("\n".join(paths))
        )

        menu.addSeparator()

        action_del = menu.addAction(
            lang.get("tree_delete_selected", "Delete {count} Items").format(
                count=len(paths),
            )
        )
        action_del.triggered.connect(lambda: self._delete_paths(paths))

        menu.exec(self.viewport().mapToGlobal(pos))

    def _show_single_context_menu(self, path: str, pos):
        lang = language_wrapper.language_word_dict
        menu = QMenu(self)
        index = self.model().index(path)
        self._add_sort_menu(menu)
        menu.addSeparator()

        # Show in Explorer
        action_explorer = menu.addAction(
            lang.get("tree_open_in_explorer", "Open in Explorer")
        )
        action_explorer.triggered.connect(lambda: self._open_in_explorer(path))

        # Open containing folder
        if Path(path).is_file():
            action_folder = menu.addAction(
                lang.get("tree_open_folder", "Open Containing Folder")
            )
            action_folder.triggered.connect(
                lambda: self._open_in_explorer(str(Path(path).parent), select=False)
            )

        # Open with system default application — useful when the user
        # wants to bounce a file to its associated editor without
        # leaving the tree.
        if Path(path).is_file():
            action_open_default = menu.addAction(
                lang.get("tree_open_with_default", "Open with Default App"),
            )
            action_open_default.triggered.connect(
                lambda: self._open_with_default_app(path),
            )

        menu.addSeparator()

        # Copy path
        action_copy = menu.addAction(lang.get("right_click_copy_path", "Copy Path"))
        action_copy.triggered.connect(
            lambda: QApplication.clipboard().setText(path)
        )

        menu.addSeparator()

        # New Folder (inside the clicked folder, or the clicked file's parent)
        action_new = menu.addAction(lang.get("tree_new_folder", "New Folder"))
        target_dir = path if Path(path).is_dir() else str(Path(path).parent)
        action_new.triggered.connect(lambda: self._create_new_folder(target_dir))

        # Refresh
        action_refresh = menu.addAction(lang.get("tree_refresh", "Refresh"))
        action_refresh.triggered.connect(self._refresh_tree)

        # Expand / collapse all children
        if Path(path).is_dir():
            action_expand = menu.addAction(lang.get("tree_expand_all", "Expand All"))
            action_expand.triggered.connect(lambda: self.expandRecursively(index))
            action_collapse = menu.addAction(lang.get("tree_collapse_all", "Collapse All"))
            action_collapse.triggered.connect(lambda: self.collapse(index))

        menu.addSeparator()

        # Rename
        action_rename = menu.addAction(lang.get("tree_rename", "Rename"))
        action_rename.setShortcut("F2")
        action_rename.triggered.connect(lambda: self._rename_path(path))

        # Duplicate
        if Path(path).is_file():
            action_dup = menu.addAction(lang.get("tree_duplicate", "Duplicate"))
            action_dup.triggered.connect(lambda: self._duplicate_file(path))

        menu.addSeparator()

        # Delete
        action_del = menu.addAction(lang.get("tree_delete", "Delete"))
        action_del.triggered.connect(lambda: self._delete_path(path))

        menu.exec(self.viewport().mapToGlobal(pos))

    def _add_sort_menu(self, menu: QMenu) -> QMenu:
        """Add file-tree sort controls to *menu*."""
        lang = language_wrapper.language_word_dict
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        sort_menu = menu.addMenu(lang.get("tree_sort_menu", "Sort Tree"))
        current_sort = user_setting_dict.get("tree_sort_by", "name")
        current_asc = bool(user_setting_dict.get("tree_sort_ascending", True))

        sort_group = QActionGroup(sort_menu)
        sort_group.setExclusive(True)
        for key in ("name", "modified", "created", "size"):
            action = sort_menu.addAction(
                lang.get(self._TREE_SORT_LANG_KEYS[key], key.capitalize()),
            )
            action.setCheckable(True)
            action.setChecked(key == current_sort)
            sort_group.addAction(action)
            action.triggered.connect(
                lambda _checked=False, k=key: self.set_tree_sort(k, current_asc),
            )

        sort_menu.addSeparator()

        order_group = QActionGroup(sort_menu)
        order_group.setExclusive(True)
        asc_action = sort_menu.addAction(lang.get("sort_ascending", "Ascending"))
        asc_action.setCheckable(True)
        asc_action.setChecked(current_asc)
        order_group.addAction(asc_action)
        asc_action.triggered.connect(
            lambda: self.set_tree_sort(
                user_setting_dict.get("tree_sort_by", "name"), True,
            ),
        )

        desc_action = sort_menu.addAction(lang.get("sort_descending", "Descending"))
        desc_action.setCheckable(True)
        desc_action.setChecked(not current_asc)
        order_group.addAction(desc_action)
        desc_action.triggered.connect(
            lambda: self.set_tree_sort(
                user_setting_dict.get("tree_sort_by", "name"), False,
            ),
        )
        return sort_menu

    def set_tree_sort(self, sort_by: str, ascending: bool) -> None:
        """Apply and persist sorting for the file tree only."""
        if sort_by not in self._TREE_SORT_COLUMNS:
            sort_by = "name"
        from Imervue.user_settings.user_setting_dict import (
            schedule_save,
            user_setting_dict,
        )
        user_setting_dict["tree_sort_by"] = sort_by
        user_setting_dict["tree_sort_ascending"] = bool(ascending)
        schedule_save()
        self._apply_tree_sort(sort_by, bool(ascending))

    def _apply_tree_sort_from_settings(self) -> None:
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        self._apply_tree_sort(
            user_setting_dict.get("tree_sort_by", "name"),
            bool(user_setting_dict.get("tree_sort_ascending", True)),
        )

    def _apply_tree_sort(self, sort_by: str, ascending: bool) -> None:
        order = (
            Qt.SortOrder.AscendingOrder
            if ascending else Qt.SortOrder.DescendingOrder
        )
        model = self.model()
        if hasattr(model, "set_sort_key"):
            # FileTreeSortProxy sorts every key (incl. creation date, which
            # QFileSystemModel has no column for) through column 0.
            model.set_sort_key(sort_by)
            self.sortByColumn(0, order)
            return
        self.sortByColumn(self._TREE_SORT_COLUMNS.get(sort_by, 0), order)

    def set_search_text(self, text: str) -> None:
        """Filter currently-loaded tree rows by basename substring."""
        self._search_text = text.strip().lower()
        self.apply_search_filter()

    def apply_search_filter(self) -> None:
        """Show only rows matching the active search or containing matches."""
        model = self.model()
        if model is None:
            return
        root = self.rootIndex()
        if not self._search_text:
            self._set_subtree_hidden(root, hidden=False)
            self.refresh_pending_hidden()
            return
        self._filter_children(root)
        self.refresh_pending_hidden()

    def _set_subtree_hidden(self, parent, *, hidden: bool) -> None:
        model = self.model()
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            self.setRowHidden(row, parent, hidden)
            self._set_subtree_hidden(index, hidden=hidden)

    def _filter_children(self, parent) -> bool:
        model = self.model()
        any_visible = False
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            child_visible = self._filter_children(index)
            own_match = self._index_matches_search(index)
            visible = own_match or child_visible
            self.setRowHidden(row, parent, not visible)
            any_visible = any_visible or visible
        return any_visible

    def _index_matches_search(self, index) -> bool:
        model = self.model()
        path = ""
        if hasattr(model, "filePath"):
            path = model.filePath(index)
        name = Path(path).name if path else str(index.data() or "")
        return self._search_text in name.lower()

    def _create_new_folder(self, parent_dir: str) -> None:
        """Prompt for a folder name and create it under ``parent_dir``."""
        from PySide6.QtWidgets import QInputDialog
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("tree_new_folder", "New Folder"),
            lang.get("tree_new_folder_prompt", "Folder name:"),
        )
        if not ok or not name.strip():
            return
        try:
            target = Path(parent_dir) / name.strip()
            target.mkdir(parents=False, exist_ok=False)
            self._refresh_tree()
        except FileExistsError:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.warning(
                    lang.get("tree_folder_exists", "Folder already exists")
                )
            return
        except OSError as exc:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.error(
                    f"{lang.get('tree_new_folder_failed', 'Create failed')}: {exc}"
                )
            return
        if hasattr(self._main_window, "toast"):
            self._main_window.toast.success(
                lang.get("tree_new_folder_done", "Created folder {name}").format(
                    name=target.name,
                ),
            )

    def _rename_path(self, path: str) -> None:
        """Prompt for a new basename and rename the file or folder."""
        from PySide6.QtWidgets import QInputDialog
        lang = language_wrapper.language_word_dict
        target = Path(path)
        if not target.exists():
            return
        new_name, ok = QInputDialog.getText(
            self,
            lang.get("tree_rename", "Rename"),
            lang.get("tree_rename_prompt", "New name:"),
            text=target.name,
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == target.name:
            return
        new_path = target.with_name(new_name)
        if new_path.exists():
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.warning(
                    lang.get("tree_rename_exists", "A file with that name already exists"),
                )
            return
        try:
            target.rename(new_path)
        except OSError as exc:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.error(
                    f"{lang.get('tree_rename_failed', 'Rename failed')}: {exc}",
                )
            return
        self._refresh_tree()
        if hasattr(self._main_window, "toast"):
            self._main_window.toast.success(
                lang.get("tree_rename_done", "Renamed to {name}").format(
                    name=new_path.name,
                ),
            )

    def _duplicate_file(self, path: str) -> None:
        """Copy ``path`` to a sibling with a "(copy)" suffix."""
        import shutil
        lang = language_wrapper.language_word_dict
        source = Path(path)
        if not source.is_file():
            return
        candidate = _next_duplicate_name(source)
        try:
            shutil.copy2(source, candidate)
        except OSError as exc:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.error(
                    f"{lang.get('tree_duplicate_failed', 'Duplicate failed')}: {exc}",
                )
            return
        self._refresh_tree()
        if hasattr(self._main_window, "toast"):
            self._main_window.toast.success(
                lang.get("tree_duplicate_done", "Duplicated to {name}").format(
                    name=candidate.name,
                ),
            )

    @staticmethod
    def _open_in_explorer(path: str, select: bool = True):
        # Static command + a local filesystem path from the file tree — no
        # untrusted input, shell=False. Bandit B603/B607 and Semgrep flag any
        # subprocess use; suppressed inline (rules are also config-skipped).
        with contextlib.suppress(Exception):
            if sys.platform == "win32":
                if select and Path(path).is_file():
                    subprocess.Popen(  # nosec B603,B607  # nosemgrep
                        ["explorer", "/select,", os.path.normpath(path)],
                    )
                else:
                    subprocess.Popen(  # nosec B603,B607  # nosemgrep
                        ["explorer", os.path.normpath(path)],
                    )
            elif sys.platform == "darwin":
                subprocess.Popen(  # nosec B603,B607  # nosemgrep
                    ["open", "-R" if select else "", path],
                )
            else:
                target = path if Path(path).is_dir() else str(Path(path).parent)
                subprocess.Popen(  # nosec B603,B607  # nosemgrep
                    ["xdg-open", target],
                )

    def _open_with_default_app(self, path: str) -> None:
        """Open ``path`` with the OS's default application via Qt's
        QDesktopServices, which is more portable than rolling per-OS
        subprocess calls. Surfaces a toast on failure so the artist
        knows whether the launch worked."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        url = QUrl.fromLocalFile(path)
        if QDesktopServices.openUrl(url):
            return
        if hasattr(self._main_window, "toast"):
            lang = language_wrapper.language_word_dict
            self._main_window.toast.error(
                lang.get(
                    "tree_open_with_failed",
                    "Couldn't open {name} with the default application",
                ).format(name=Path(path).name),
            )

    def _delete_paths(self, paths: list[str]) -> None:
        """Send every existing path in *paths* to the trash.

        For a single path this defers to ``_delete_path`` so the existing
        per-file toast is preserved; for a batch the individual toasts are
        suppressed and replaced with one summary so the user isn't spammed.
        Every batch runs its OS-trash calls on a background worker, in
        grouped shell operations — one ``send2trash`` call costs ~0.27 s
        regardless of how few files it carries, so even a handful deleted
        one at a time stalls the GUI for seconds.
        """
        existing = [p for p in paths if Path(p).exists()]
        if not existing:
            return
        if len(existing) == 1:
            self._delete_path(existing[0])
            return
        self._delete_batch_async(existing)

    def _delete_batch_async(self, existing: list[str]) -> None:
        """Batch delete: soft-delete in memory, trash on a worker."""
        viewer = self._main_window.viewer
        in_list, folders, loose = _partition_delete_batch(
            existing, viewer.model.images)
        if in_list:
            self._batch_delete_from_viewer_list(in_list, viewer)
        if folders:
            for folder in folders:
                self._soft_delete_folder(folder, notify=False, refresh=False)
            # One re-sync for the whole batch. refresh_pending_hidden costs
            # a model lookup per pending path, so refreshing inside the loop
            # is quadratic and stalls the tree on a large folder selection.
            self.refresh_pending_hidden()
        if not loose:
            self._notify_deleted_batch(len(existing))
            return
        self._trash_in_background(loose, already_removed=len(existing) - len(loose))

    def _batch_delete_from_viewer_list(self, paths: list[str], viewer) -> None:
        """Soft-delete many viewer-list files in one pass.

        One list rebuild, one undo entry, and one GL pass — the per-file
        variant costs O(images) per path plus a GL context switch each,
        which visibly hangs the UI on large selections.
        """
        images = viewer.model.images
        doomed = set(paths)
        removed = [(idx, path) for idx, path in enumerate(images) if path in doomed]
        if not removed:
            return
        images[:] = [path for path in images if path not in doomed]
        viewer.undo_stack.append({
            "mode": "delete",
            "deleted_paths": [path for _idx, path in removed],
            "indices": [idx for idx, _path in removed],
            "restored": False,
        })
        self._release_tile_textures(viewer, [path for _idx, path in removed])
        for _idx, path in removed:
            viewer.tile_cache.pop(path, None)
        self._refresh_viewer_after_delete(viewer, images, removed[0][0])

    def _trash_in_background(self, paths: list[str], already_removed: int) -> None:
        """Move *paths* to the OS trash on a worker thread; toast on finish."""
        from Imervue.system.trash_ops import FileDeleteWorker
        worker = FileDeleteWorker(paths, parent=self)
        worker.progress.connect(self._on_trash_progress)
        worker.finished_with.connect(
            lambda done, failed, w=worker:
            self._on_trash_finished(w, done, failed, already_removed),
        )
        self._trash_workers.add(worker)
        worker.start()

    def _on_trash_progress(self, done: int, total: int) -> None:
        if hasattr(self._main_window, "show_progress"):
            self._main_window.show_progress(done, total)

    def _on_trash_finished(self, worker, done: list[str], failed: list[str],
                           already_removed: int) -> None:
        self._trash_workers.discard(worker)
        worker.deleteLater()
        self._notify_deleted_batch(len(done) + already_removed)
        if failed and hasattr(self._main_window, "toast"):
            lang = language_wrapper.language_word_dict
            self._main_window.toast.warning(
                lang.get(
                    "tree_delete_failed_count",
                    "Couldn't delete {count} item(s)",
                ).format(count=len(failed)),
            )

    def shutdown(self) -> None:
        """Wait for any in-flight OS-trash workers so their QThreads aren't
        destroyed mid-run when this view (or its owning window) is torn down.

        FileDeleteWorker is parented to this view; without this a secondary
        window closing (which deleteLater's the view) would destroy a running
        worker thread ('QThread: Destroyed while thread is still running'), and
        the primary window's os._exit would abort an in-flight OS-trash batch
        partway. The main window calls this from closeEvent before teardown.
        """
        for worker in list(self._trash_workers):
            with contextlib.suppress(RuntimeError):
                if worker.isRunning():
                    worker.wait()
        self._trash_workers.clear()

    def _delete_path(self, path: str, notify: bool = True):
        if not Path(path).exists():
            return
        viewer = self._main_window.viewer
        images = viewer.model.images
        if Path(path).is_file() and path in images:
            self._delete_from_viewer_list(path, viewer, images, notify=notify)
        else:
            self._delete_external(path, notify=notify)

    def _delete_from_viewer_list(
        self, path: str, viewer, images: list[str], notify: bool = True,
    ) -> None:
        idx = images.index(path)
        images.pop(idx)
        viewer.undo_stack.append({
            "mode": "delete",
            "deleted_paths": [path],
            "indices": [idx],
            "restored": False,
        })
        self._release_tile_textures(viewer, [path])
        viewer.tile_cache.pop(path, None)
        self._refresh_viewer_after_delete(viewer, images, idx)
        if notify:
            self._notify_deleted(path)

    @staticmethod
    def _release_tile_textures(viewer, paths: list[str]) -> None:
        """Free the GL textures for *paths* under a single context switch and
        keep the viewer's VRAM accounting in sync.

        The delete fires from a menu-action event handler, not from within
        ``paintGL``, so the viewer's GL context may not be current. Make it
        current once for the whole batch and swallow the GLError if the
        context is gone entirely (window already destroyed during shutdown).
        Like ``tile_textures.free_tile_textures``, drop each freed path from
        ``_tile_tex_sizes`` and subtract its bytes from ``_vram_usage`` —
        omitting that desynced the budget upward on every tree delete until
        new tile uploads were refused (the blank-wall symptom).
        """
        sizes = getattr(viewer, "_tile_tex_sizes", None)
        textures = []
        freed_bytes = 0
        for p in paths:
            tex = viewer.tile_textures.pop(p, None)
            if tex is None:
                continue
            textures.append(tex)
            if sizes is not None:
                freed_bytes += sizes.pop(p, 0)
        if not textures:
            return
        from OpenGL.GL import glDeleteTextures
        from PySide6.QtGui import QOpenGLContext
        try:
            if hasattr(viewer, "makeCurrent"):
                viewer.makeCurrent()
            if QOpenGLContext.currentContext() is not None:
                glDeleteTextures(textures)
        except Exception:   # nosec B110  # noqa: BLE001, S110 — GL context torn down; nothing to log
            pass
        finally:
            if hasattr(viewer, "doneCurrent"):
                viewer.doneCurrent()
        if hasattr(viewer, "_vram_usage"):
            viewer._vram_usage = max(0, viewer._vram_usage - freed_bytes)

    @staticmethod
    def _refresh_viewer_after_delete(viewer, images: list[str], idx: int) -> None:
        if viewer.tile_grid_mode:
            viewer.tile_rects.clear()
            viewer.update()
            return
        if not viewer.deep_zoom:
            return
        if images:
            viewer.current_index = min(idx, len(images) - 1)
            viewer.load_deep_zoom_image(images[viewer.current_index])
        else:
            viewer.deep_zoom = None
            viewer.current_index = 0
            viewer.tile_grid_mode = True
            viewer.update()

    def _delete_external(self, path: str, notify: bool = True) -> None:
        # Folders go through the app Recycle Bin (kept on disk + hidden, sent to
        # the OS trash only at shutdown) so they are restorable in-app; loose
        # non-list files still go straight to the OS trash.
        if Path(path).is_dir():
            self._soft_delete_folder(path, notify=notify)
            return
        from Imervue.gpu_image_view.actions.keyboard_actions import _send_to_trash
        if _send_to_trash(path) and notify:
            self._notify_deleted(path)

    def _soft_delete_folder(self, path: str, notify: bool = True, *,
                            refresh: bool = True) -> None:
        """Hide *path* pending deletion. ``refresh=False`` lets a batch
        caller re-sync the hidden rows once instead of once per folder."""
        viewer = self._main_window.viewer
        viewer.undo_stack.append({
            "mode": "delete_external",
            "deleted_paths": [path],
            "restored": False,
        })
        if refresh:
            self.refresh_pending_hidden()
        if notify and hasattr(self._main_window, "toast"):
            lang = language_wrapper.language_word_dict
            self._main_window.toast.info(
                lang.get("tree_recycled", "Moved to Recycle Bin: {name}").format(
                    name=Path(path).name,
                ),
            )

    def _notify_deleted(self, path: str) -> None:
        if not hasattr(self._main_window, "toast"):
            return
        lang = language_wrapper.language_word_dict
        self._main_window.toast.info(
            lang.get("tree_deleted", "Moved to trash: {name}").format(
                name=Path(path).name
            )
        )

    def _notify_deleted_batch(self, count: int) -> None:
        """One summary toast after a multi-file delete."""
        if not hasattr(self._main_window, "toast"):
            return
        lang = language_wrapper.language_word_dict
        self._main_window.toast.info(
            lang.get("tree_deleted_batch", "Moved {count} items to trash").format(
                count=count,
            )
        )
