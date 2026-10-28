"""Build selection-dependent file-tree context menus."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QApplication, QFileSystemModel, QMenu
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.file_manager import reveal_or_warn


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

    action_explorer = menu.addAction(lang.get("tree_open_in_explorer", "Open in Explorer"))
    action_explorer.triggered.connect(lambda: reveal_or_warn(paths[0]))

    action_copy = menu.addAction(lang.get("tree_copy_paths", "Copy Paths"))
    action_copy.triggered.connect(lambda: QApplication.clipboard().setText("\n".join(paths)))

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
    action_explorer = menu.addAction(lang.get("tree_open_in_explorer", "Open in Explorer"))
    action_explorer.triggered.connect(lambda: reveal_or_warn(path))

    # Open containing folder
    if Path(path).is_file():
        action_folder = menu.addAction(lang.get("tree_open_folder", "Open Containing Folder"))
        action_folder.triggered.connect(
            lambda: reveal_or_warn(str(Path(path).parent), select=False)
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
    action_copy.triggered.connect(lambda: QApplication.clipboard().setText(path))

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
