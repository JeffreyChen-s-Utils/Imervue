"""
篩選選單
Filter menu — filter displayed images by file extension or rating.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMenu

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

# 支援的分類
_EXT_GROUPS = {
    "all": None,
    "jpg": {".jpg", ".jpeg"},
    "png": {".png"},
    "bmp": {".bmp"},
    "tiff": {".tiff", ".tif"},
    "svg": {".svg"},
    "raw": {".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"},
}


def build_filter_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict

    filter_menu = ui.menuBar().addMenu(lang.get("filter_menu_title", "Filter"))

    # ===== 依副檔名 =====
    ext_menu = filter_menu.addMenu(lang.get("filter_by_extension", "By Extension"))
    for key in _EXT_GROUPS:
        label = lang.get(f"filter_ext_{key}", key.upper() if key != "all" else "All")
        action = ext_menu.addAction(label)
        action.triggered.connect(lambda checked, k=key: _apply_ext_filter(ui, k))

    # ===== 依評分 =====
    rating_menu = filter_menu.addMenu(lang.get("filter_by_rating", "By Rating"))
    action_all = rating_menu.addAction(lang.get("filter_rating_all", "All"))
    action_all.triggered.connect(lambda: _apply_rating_filter(ui, 0))

    action_fav = rating_menu.addAction(lang.get("filter_rating_favorited", "Favorited"))
    action_fav.triggered.connect(lambda: _apply_rating_filter(ui, -1))

    for star in range(1, 6):
        label = "\u2605" * star
        action = rating_menu.addAction(label)
        action.triggered.connect(lambda checked, s=star: _apply_rating_filter(ui, s))

    filter_menu.addSeparator()

    # ===== 清除篩選 =====
    clear_action = filter_menu.addAction(lang.get("filter_clear", "Clear Filter"))
    clear_action.triggered.connect(lambda: _clear_filter(ui))

    ui._filter_menu = filter_menu
    return filter_menu


def _apply_ext_filter(ui: ImervueMainWindow, ext_key: str):
    viewer = ui.viewer
    all_images = _get_full_image_list(viewer)
    if not all_images:
        return

    exts = _EXT_GROUPS.get(ext_key)
    if exts is None:
        filtered = all_images
    else:
        filtered = [p for p in all_images if Path(p).suffix.lower() in exts]

    if not filtered:
        return

    viewer.clear_tile_grid()
    viewer.load_tile_grid_async(filtered)


def _apply_rating_filter(ui: ImervueMainWindow, min_rating: int):
    viewer = ui.viewer
    all_images = _get_full_image_list(viewer)
    if not all_images:
        return

    ratings = user_setting_dict.get("image_ratings", {})
    favorites = user_setting_dict.get("image_favorites", set())

    if min_rating == 0:
        filtered = all_images
    elif min_rating == -1:
        # Favorited only
        filtered = [p for p in all_images if p in favorites or ratings.get(p, 0) > 0]
    else:
        filtered = [p for p in all_images if ratings.get(p, 0) >= min_rating]

    if not filtered:
        return

    viewer.clear_tile_grid()
    viewer.load_tile_grid_async(filtered)


def _clear_filter(ui: ImervueMainWindow):
    viewer = ui.viewer
    all_images = _get_full_image_list(viewer)
    if all_images:
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(all_images)


def _get_full_image_list(viewer) -> list[str]:
    """取得完整的圖片列表（未篩選前的）"""
    if hasattr(viewer, '_unfiltered_images') and viewer._unfiltered_images:
        return list(viewer._unfiltered_images)
    return list(viewer.model.images)
