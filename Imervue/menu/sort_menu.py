"""
排序選單
Sort menu — allows sorting images by name, date, size, resolution.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMenu

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


# ===========================
# 排序鍵函式
# ===========================

def _sort_key_name(path: str):
    return Path(path).name.lower()


def _sort_key_modified(path: str):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def _sort_key_created(path: str):
    try:
        return os.path.getctime(path)
    except OSError:
        return 0


def _sort_key_size(path: str):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _sort_key_resolution(path: str):
    try:
        with Image.open(path) as img:
            w, h = img.size
            return w * h
    except Exception:
        return 0


_SORT_KEYS = {
    "name": _sort_key_name,
    "modified": _sort_key_modified,
    "created": _sort_key_created,
    "size": _sort_key_size,
    "resolution": _sort_key_resolution,
}

_SORT_LANG_KEYS = {
    "name": "sort_by_name",
    "modified": "sort_by_modified",
    "created": "sort_by_created",
    "size": "sort_by_size",
    "resolution": "sort_by_resolution",
}


# ===========================
# 執行排序
# ===========================

def apply_sort(main_window: ImervueMainWindow, sort_by: str, ascending: bool):
    viewer = main_window.viewer
    images = viewer.model.images
    if not images:
        return

    key_fn = _SORT_KEYS.get(sort_by, _sort_key_name)
    images.sort(key=key_fn, reverse=not ascending)

    user_setting_dict["sort_by"] = sort_by
    user_setting_dict["sort_ascending"] = ascending

    # 重新載入 tile grid
    if viewer.tile_grid_mode:
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(images)


# ===========================
# 建立選單
# ===========================

def build_sort_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict

    sort_menu = ui.menuBar().addMenu(lang.get("sort_menu_title", "Sort"))

    sort_group = QActionGroup(ui)
    sort_group.setExclusive(True)

    current_sort = user_setting_dict.get("sort_by", "name")
    current_asc = user_setting_dict.get("sort_ascending", True)

    for key in ("name", "modified", "created", "size", "resolution"):
        lang_key = _SORT_LANG_KEYS[key]
        default = key.capitalize()
        action = sort_menu.addAction(lang.get(lang_key, default))
        action.setCheckable(True)
        if key == current_sort:
            action.setChecked(True)
        sort_group.addAction(action)
        action.triggered.connect(
            lambda checked, k=key: _on_sort_selected(ui, k)
        )

    sort_menu.addSeparator()

    # 升序 / 降序
    order_group = QActionGroup(ui)
    order_group.setExclusive(True)

    asc_action = sort_menu.addAction(lang.get("sort_ascending", "Ascending"))
    asc_action.setCheckable(True)
    asc_action.setChecked(current_asc)
    order_group.addAction(asc_action)

    desc_action = sort_menu.addAction(lang.get("sort_descending", "Descending"))
    desc_action.setCheckable(True)
    desc_action.setChecked(not current_asc)
    order_group.addAction(desc_action)

    asc_action.triggered.connect(lambda: _on_order_changed(ui, True))
    desc_action.triggered.connect(lambda: _on_order_changed(ui, False))

    # 儲存參照方便後續更新
    ui._sort_menu = sort_menu

    return sort_menu


def _on_sort_selected(ui: ImervueMainWindow, sort_by: str):
    ascending = user_setting_dict.get("sort_ascending", True)
    apply_sort(ui, sort_by, ascending)


def _on_order_changed(ui: ImervueMainWindow, ascending: bool):
    sort_by = user_setting_dict.get("sort_by", "name")
    apply_sort(ui, sort_by, ascending)
