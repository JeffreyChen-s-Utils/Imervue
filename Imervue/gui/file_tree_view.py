"""Qt file-tree event handling and explicit bindings of tree operations.

The view owns selection, hidden paths, and trash-worker lifetime. Operation
functions retain normal method dispatch, including instance and subclass overrides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from PySide6.QtCore import QSignalBlocker, QSize, Qt, Signal
from PySide6.QtWidgets import QFileSystemModel, QTreeView
from Imervue.gui.file_tree_paths import _dedupe_paths, _next_duplicate_name, _partition_delete_batch
from Imervue.gui.file_tree_preferences import sort_settings
from Imervue.gui.file_tree_sort_controls import FileTreeSortMixin
from Imervue.gui.file_tree_state import FileTreeState
from Imervue.gui.file_tree_trash import _TrashRequest
from Imervue.gui.folder_thumbnail_model import clamp_icon_size

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

__all__ = [
    "_FileTreeView",
    "_next_duplicate_name",
    "_partition_delete_batch",
    "_dedupe_paths",
    "_TrashRequest",
]


class _FileTreeView(FileTreeSortMixin, QTreeView):
    """File-tree widget with selection-aware commands and queued deletion.

    Sorting (``_TREE_SORT_COLUMNS``, ``set_tree_sort``, the sort menu and
    controls) comes from ``FileTreeSortMixin``; nothing below redefines it.
    """

    tree_sort_changed = Signal(str, bool)
    search_path_activated = Signal(str)

    _ZOOM_STEP = 8  # px per Ctrl+wheel notch when resizing folder thumbnails

    from Imervue.gui.file_tree_menus import (
        _show_context_menu,
        _show_tree_context_menu,
        _show_multi_context_menu,
        _show_single_context_menu,
    )
    from Imervue.gui.file_tree_filter import (
        _refresh_tree,
        set_search_text,
        apply_search_filter,
        _set_subtree_hidden,
        _filter_children,
        _index_matches_search,
    )
    from Imervue.gui.file_tree_recycle import (
        refresh_pending_hidden,
        _set_row_hidden,
        _soft_delete_folder,
    )
    from Imervue.gui.file_tree_commands import (
        _create_new_folder,
        _rename_path,
        _duplicate_file,
        _open_with_default_app,
    )
    from Imervue.gui.file_tree_delete import (
        _delete_paths,
        _delete_batch_async,
        _delete_path,
        _delete_external,
    )
    from Imervue.gui.file_tree_viewer_delete import (
        _batch_delete_from_viewer_list,
        _delete_from_viewer_list,
        _notify_plugins_deleted,
        _refresh_viewer_after_delete,
    )
    from Imervue.gui.file_tree_textures import (
        _release_tile_textures,
    )
    from Imervue.gui.file_tree_trash import (
        _trash_in_background,
        _pump_trash_queue,
        _on_trash_finished,
        shutdown,
        _flush_pending_trash,
    )
    from Imervue.gui.file_tree_feedback import (
        _on_trash_progress,
        _notify_batch_result,
        _notify_single_result,
        _notify_deleted,
        _notify_deleted_batch,
    )

    _release_tile_textures = staticmethod(_release_tile_textures)
    _refresh_viewer_after_delete = staticmethod(_refresh_viewer_after_delete)

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__()
        self._main_window = main_window
        self._search_text = ""
        self._tree_state = FileTreeState(self)
        self._recursive_search = None
        # Global defaults until a root is shown; setModel/setRootIndex reload them.
        self._sort_settings = sort_settings(self._sort_root())
        # Folders pending soft-deletion are kept on disk but hidden from the
        # tree until restored or committed at shutdown; track what we hid so a
        # restore can un-hide exactly those rows.
        self._hidden_paths: set[str] = set()
        # In-flight background trash workers — referenced here so they are
        # not garbage-collected mid-run; each self-evicts on finish.
        self._trash_workers: set = set()
        # Trash asks waiting for the in-flight worker; drained as one batch.
        self._pending_trash: list[_TrashRequest] = []
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        # Ctrl/Shift multi-select so batch delete / copy-paths can act on
        # several files at once. A plain single click still selects and
        # opens one file via the main window's ``clicked`` handler.
        self.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QTreeView.ScrollMode.ScrollPerPixel)
        self.setSortingEnabled(True)
        self.header().sortIndicatorChanged.connect(self._on_sort_indicator_changed)

    def setModel(self, model) -> None:
        with QSignalBlocker(self.header()):
            super().setModel(model)
        # Re-apply the pending-delete hidden rows whenever a directory finishes
        # (re)loading, so navigating away and back keeps deleted folders hidden.
        loaded = getattr(model, "directoryLoaded", None)
        if loaded is not None:
            loaded.connect(lambda _path: self.refresh_pending_hidden())
            loaded.connect(lambda _path: self.apply_search_filter())
        with QSignalBlocker(self.header()):
            self._apply_tree_sort_from_settings()
        self._tree_state.bind_model(model)

    def set_root_path(self, path: str, *, refresh: bool = False) -> None:
        """Show *path* as the tree root, saving the old root's view state first.

        ``refresh`` clears the model root first: setRootPath() only re-stats
        a directory when the value changes.
        """
        self._tree_state.save()
        if self._recursive_search is not None:
            self._recursive_search.cancel()
        model = self.model()
        if refresh:
            self._tree_state.begin_refresh()
            model.setRootPath("")
        model.setRootPath(path)
        self.setRootIndex(model.index(path))

    def setRootIndex(self, index) -> None:
        super().setRootIndex(index)
        self._tree_state.set_root(self.model().filePath(index) if index.isValid() else "")
        self._apply_tree_sort_from_settings()
        if self._recursive_search is not None:
            self._recursive_search.root_changed()

    def create_search_controls(self):
        """Build the recursive-search panel bound to this tree."""
        from Imervue.gui.file_tree_search import FileTreeSearch

        self._recursive_search = FileTreeSearch(self)
        self._recursive_search.path_activated.connect(self.search_path_activated)
        return self._recursive_search.panel

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

    def refresh(self) -> None:
        """Re-read the shown folders from disk; the main window calls it (``_refresh_tree``)."""
        self._refresh_tree()

    def _delete_selected(self):
        self._delete_paths(self._selected_paths())
