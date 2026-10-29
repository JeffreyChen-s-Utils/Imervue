"""File-tree sorting UI with global defaults and explicit folder overrides."""
from dataclasses import replace

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QMenu, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from Imervue.gui.file_tree_preferences import (
    folder_overrides, root_key, save_sort_settings, set_folder_override, sort_settings,
)
from Imervue.gui.file_tree_sort import TREE_SORT_KEYS, normalize_sort_key
from Imervue.multi_language.language_wrapper import language_wrapper

SORT_LABELS = {
    "name": "sort_by_name", "modified": "sort_by_modified", "created": "sort_by_created",
    "size": "sort_by_size", "type": "tree_sort_type",
}
CONTROL_LABELS = {
    **SORT_LABELS, "modified": "tree_metadata_modified",
    "created": "tree_metadata_created", "size": "tree_metadata_size",
}


def direction_label(key: str, ascending: bool) -> str:
    """Describe the visible order using the selected field's meaning."""
    labels = {
        "modified": (("sort_oldest_first", "Oldest first"), ("sort_newest_first", "Newest first")),
        "created": (("sort_oldest_first", "Oldest first"), ("sort_newest_first", "Newest first")),
        "size": (("sort_smallest_first", "Smallest first"),
                 ("sort_largest_first", "Largest first")),
    }
    order = labels.get(key, (("sort_a_to_z", "A → Z"), ("sort_z_to_a", "Z → A")))
    lang_key, fallback = order[0 if ascending else 1]
    return language_wrapper.language_word_dict.get(lang_key, fallback)


class _SortControls(QWidget):
    def __init__(self, tree):
        super().__init__()
        self.tree = tree
        self.lang = language_wrapper.language_word_dict
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox()
        self.combo.setObjectName("treeSortBy")
        self.combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.combo.setAccessibleName(self.lang.get("tree_sort_menu", "Sort Tree"))
        for key in TREE_SORT_KEYS:
            self.combo.addItem(self.lang.get(CONTROL_LABELS[key], key.capitalize()), key)
        self.direction = QToolButton()
        self.direction.setObjectName("treeSortDirection")
        self.direction.setCheckable(True)
        self.direction.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.combo)
        layout.addWidget(self.direction)
        self.scope = QComboBox()
        self.scope.setObjectName("treeSortScope")
        self.scope.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.scope.setAccessibleName(self.lang.get("tree_sort_scope", "Sorting scope"))
        self.scope.addItem(self.lang.get("tree_sort_global", "Global"), False)
        self.scope.addItem(self.lang.get("tree_sort_this_folder", "This folder"), True)
        self.reset = QToolButton()
        self.reset.setObjectName("treeSortReset")
        self.reset.setText(self.lang.get("tree_sort_reset_short", "Reset"))
        self.reset.setToolTip(self.lang.get("tree_sort_reset", "Reset to global sorting"))
        self.reset.setAccessibleName(self.reset.toolTip())
        layout.addWidget(self.scope)
        actions = QHBoxLayout()
        actions.addWidget(self.reset, 1)
        actions.addWidget(self._options())
        layout.addLayout(actions)
        self.sync(tree._sort_settings.key, tree._sort_settings.ascending)
        self.combo.currentIndexChanged.connect(
            lambda: tree.set_tree_sort(self.combo.currentData(), tree._sort_settings.ascending))
        self.direction.toggled.connect(
            lambda checked: tree.set_tree_sort(tree._sort_settings.key, not checked))
        self.scope.currentIndexChanged.connect(
            lambda: tree.set_folder_sort_override(self.scope.currentData()))
        self.reset.clicked.connect(lambda: tree.set_folder_sort_override(False))
        tree.tree_sort_changed.connect(self.sync)

    def _options(self) -> QToolButton:
        options = QToolButton()
        options.setObjectName("treeSortOptions")
        options.setText("⋯")
        options.setToolTip(self.lang.get("tree_sort_options", "Sorting options"))
        options.setAccessibleName(options.toolTip())
        options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(options)
        options.setMenu(menu)
        menu.aboutToShow.connect(lambda: self.tree._populate_sort_options(menu))
        return options

    def sync(self, key: str, ascending: bool) -> None:
        own = root_key(self.tree._sort_root()) in folder_overrides()
        with QSignalBlocker(self.combo), QSignalBlocker(self.direction), QSignalBlocker(self.scope):
            self.combo.setCurrentIndex(self.combo.findData(key))
            self.direction.setChecked(not ascending)
            self.direction.setText(direction_label(key, ascending))
            self.direction.setToolTip(self.direction.text())
            self.direction.setAccessibleName(self.direction.text())
            self.scope.setCurrentIndex(1 if own else 0)
            self.scope.setEnabled(bool(self.tree._sort_root()))
            self.reset.setEnabled(own)


class FileTreeSortMixin:
    _TREE_SORT_COLUMNS = {"name": 0, "size": 1, "modified": 3, "created": 3, "type": 2}
    _TREE_SORT_LANG_KEYS = SORT_LABELS

    def _sort_root(self) -> str:
        return self._tree_state.root

    def _on_sort_indicator_changed(self, _column: int, order: Qt.SortOrder) -> None:
        self.set_tree_sort(self._sort_settings.key, order == Qt.SortOrder.AscendingOrder)

    def create_sort_controls(self) -> QWidget:
        return _SortControls(self)

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
        """Apply and persist sorting; a subclass's ``_TREE_SORT_COLUMNS`` validates the key."""
        key = sort_by if sort_by in self._TREE_SORT_COLUMNS else normalize_sort_key(sort_by)
        self._sort_settings = replace(self._sort_settings, key=key, ascending=bool(ascending))
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
