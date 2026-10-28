"""File-tree sorting UI with global defaults and explicit folder overrides."""
from dataclasses import replace

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QMenu, QSizePolicy, QToolButton, QWidget

from Imervue.gui.file_tree_preferences import (
    folder_overrides, root_key, save_sort_settings, set_folder_override, sort_settings,
)
from Imervue.gui.file_tree_sort import TREE_SORT_KEYS, normalize_sort_key
from Imervue.multi_language.language_wrapper import language_wrapper

SORT_LABELS = {
    "name": "sort_by_name", "modified": "sort_by_modified", "created": "sort_by_created",
    "size": "sort_by_size", "type": "tree_sort_type",
}


class FileTreeSortMixin:
    _TREE_SORT_COLUMNS = {"name": 0, "size": 1, "modified": 3, "created": 3, "type": 2}
    _TREE_SORT_LANG_KEYS = SORT_LABELS

    def _sort_root(self) -> str:
        return self._tree_state.root

    def _on_sort_indicator_changed(self, _column: int, order: Qt.SortOrder) -> None:
        self.set_tree_sort(self._sort_settings.key, order == Qt.SortOrder.AscendingOrder)

    def create_sort_controls(self) -> QWidget:
        lang = language_wrapper.language_word_dict
        controls = QWidget()
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        combo = QComboBox()
        combo.setObjectName("treeSortBy")
        combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        combo.setAccessibleName(lang.get("tree_sort_menu", "Sort Tree"))
        combo.setToolTip(combo.accessibleName())
        for key in TREE_SORT_KEYS:
            combo.addItem(lang.get(SORT_LABELS[key], key.capitalize()), key)
        direction = QToolButton()
        direction.setObjectName("treeSortDirection")
        direction.setCheckable(True)
        options = QToolButton()
        options.setObjectName("treeSortOptions")
        options.setText("⋯")
        options.setToolTip(lang.get("tree_sort_options", "Sorting options"))
        options.setAccessibleName(options.toolTip())
        options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(options)
        options.setMenu(menu)
        menu.aboutToShow.connect(lambda: self._populate_sort_options(menu))

        def sync(key: str, ascending: bool) -> None:
            with QSignalBlocker(combo), QSignalBlocker(direction):
                combo.setCurrentIndex(combo.findData(key))
                direction.setChecked(not ascending)
                direction.setText("↑" if ascending else "↓")
                label = lang.get("sort_ascending" if ascending else "sort_descending",
                                 "Ascending" if ascending else "Descending")
                direction.setToolTip(label)
                direction.setAccessibleName(label)

        sync(self._sort_settings.key, self._sort_settings.ascending)
        combo.currentIndexChanged.connect(
            lambda: self.set_tree_sort(combo.currentData(), self._sort_settings.ascending))
        direction.toggled.connect(
            lambda checked: self.set_tree_sort(self._sort_settings.key, not checked))
        self.tree_sort_changed.connect(sync)
        layout.addWidget(combo, 1)
        layout.addWidget(direction)
        layout.addWidget(options)
        return controls

    def _populate_sort_options(self, menu: QMenu) -> None:
        menu.clear()
        lang = language_wrapper.language_word_dict
        folders = menu.addAction(lang.get("tree_folders_first", "Folders first"))
        folders.setCheckable(True)
        folders.setChecked(self._sort_settings.folders_first)
        folders.triggered.connect(self.set_folders_first)
        own = menu.addAction(lang.get("tree_folder_sort", "Use folder-specific sorting"))
        own.setCheckable(True)
        own.setChecked(root_key(self._sort_root()) in folder_overrides())
        own.setEnabled(bool(self._sort_root()))
        own.triggered.connect(self.set_folder_sort_override)
        reset = menu.addAction(lang.get("tree_sort_reset", "Reset to global sorting"))
        reset.setEnabled(own.isChecked())
        reset.triggered.connect(lambda: self.set_folder_sort_override(False))

    def _add_sort_menu(self, menu: QMenu) -> QMenu:
        lang = language_wrapper.language_word_dict
        sort_menu = menu.addMenu(lang.get("tree_sort_menu", "Sort Tree"))
        group = QActionGroup(sort_menu)
        group.setExclusive(True)
        for key in TREE_SORT_KEYS:
            action = sort_menu.addAction(lang.get(SORT_LABELS[key], key.capitalize()))
            action.setData(key)
            action.setCheckable(True)
            action.setChecked(key == self._sort_settings.key)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, k=key: self.set_tree_sort(
                k, self._sort_settings.ascending))
        sort_menu.addSeparator()
        orders = QActionGroup(sort_menu)
        orders.setExclusive(True)
        for ascending, label in ((True, "sort_ascending"), (False, "sort_descending")):
            action = sort_menu.addAction(lang.get(label, label))
            action.setCheckable(True)
            action.setChecked(ascending == self._sort_settings.ascending)
            orders.addAction(action)
            action.triggered.connect(lambda _checked=False, a=ascending: self.set_tree_sort(
                self._sort_settings.key, a))
        options = sort_menu.addMenu(lang.get("tree_sort_options", "Sorting options"))
        self._populate_sort_options(options)
        return sort_menu

    def set_tree_sort(self, sort_by: str, ascending: bool) -> None:
        self._sort_settings = replace(self._sort_settings, key=normalize_sort_key(sort_by),
                                      ascending=bool(ascending))
        self._save_and_apply_sort()

    def set_folders_first(self, enabled: bool) -> None:
        self._sort_settings = replace(self._sort_settings, folders_first=bool(enabled))
        self._save_and_apply_sort()

    def set_folder_sort_override(self, enabled: bool) -> None:
        set_folder_override(self._sort_root(), self._sort_settings if enabled else None)
        self._apply_tree_sort_from_settings()

    def _save_and_apply_sort(self) -> None:
        save_sort_settings(self._sort_root(), self._sort_settings)
        self._apply_tree_sort(self._sort_settings.key, self._sort_settings.ascending)

    def _apply_tree_sort_from_settings(self) -> None:
        self._sort_settings = sort_settings(self._sort_root())
        self._apply_tree_sort(self._sort_settings.key, self._sort_settings.ascending)

    def _apply_tree_sort(self, sort_by: str, ascending: bool) -> None:
        order = Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder
        model = self.model()
        with QSignalBlocker(self.header()):
            if hasattr(model, "set_sort_key"):
                model.set_folders_first(self._sort_settings.folders_first)
                model.set_sort_key(sort_by)
                self.sortByColumn(0, order)
            else:
                self.sortByColumn(self._TREE_SORT_COLUMNS.get(sort_by, 0), order)
        self.tree_sort_changed.emit(sort_by, ascending)
