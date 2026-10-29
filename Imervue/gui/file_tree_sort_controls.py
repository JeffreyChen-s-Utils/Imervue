"""Apply and persist file-tree sort and thumbnail settings."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMenu
from Imervue.gui.folder_thumbnail_model import clamp_icon_size
from Imervue.multi_language.language_wrapper import language_wrapper


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
            user_setting_dict.get("tree_sort_by", "name"),
            True,
        ),
    )

    desc_action = sort_menu.addAction(lang.get("sort_descending", "Descending"))
    desc_action.setCheckable(True)
    desc_action.setChecked(not current_asc)
    order_group.addAction(desc_action)
    desc_action.triggered.connect(
        lambda: self.set_tree_sort(
            user_setting_dict.get("tree_sort_by", "name"),
            False,
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
    order = Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder
    model = self.model()
    if hasattr(model, "set_sort_key"):
        # FileTreeSortProxy sorts every key (incl. creation date, which
        # QFileSystemModel has no column for) through column 0.
        model.set_sort_key(sort_by)
        self.sortByColumn(0, order)
        return
    self.sortByColumn(self._TREE_SORT_COLUMNS.get(sort_by, 0), order)
