"""
篩選選單
Filter menu — filter displayed images by file extension or rating.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


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

    # ===== 依色彩標籤 =====
    color_menu = filter_menu.addMenu(lang.get("filter_by_color", "By Color Label"))
    color_all = color_menu.addAction(lang.get("filter_color_all", "All"))
    color_all.triggered.connect(lambda: _apply_color_filter(ui, None))
    color_any = color_menu.addAction(lang.get("filter_color_any", "Any label"))
    color_any.triggered.connect(lambda: _apply_color_filter(ui, "any"))
    color_none = color_menu.addAction(lang.get("filter_color_none", "No label"))
    color_none.triggered.connect(lambda: _apply_color_filter(ui, "none"))
    color_menu.addSeparator()
    for c in ("red", "yellow", "green", "blue", "purple"):
        a = color_menu.addAction(lang.get(f"color_label_{c}", c.title()))
        a.triggered.connect(lambda checked, cc=c: _apply_color_filter(ui, cc))

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

    # ===== 依標籤 =====
    tag_menu = filter_menu.addMenu(lang.get("filter_by_tag", "By Tag"))
    _build_tag_filter(ui, tag_menu)

    # ===== 依相簿 =====
    album_menu = filter_menu.addMenu(lang.get("filter_by_album", "By Album"))
    _build_album_filter(ui, album_menu)

    filter_menu.addSeparator()

    # ===== 多標籤過濾 (AND/OR) =====
    multi_tag_action = filter_menu.addAction(
        lang.get("filter_multi_tag", "Multi-Tag Filter…")
    )
    multi_tag_action.triggered.connect(lambda: _open_multi_tag(ui))

    # ===== 進階過濾 =====
    adv_action = filter_menu.addAction(
        lang.get("filter_advanced", "Advanced Filter…")
    )
    adv_action.triggered.connect(lambda: _open_advanced(ui))

    filter_menu.addSeparator()

    # ===== 分揀 (Pick / Reject / Unflagged) =====
    cull_menu = filter_menu.addMenu(lang.get("filter_by_cull", "By Cull State"))
    cull_all = cull_menu.addAction(lang.get("filter_cull_all", "All"))
    cull_all.triggered.connect(lambda: _apply_cull_filter(ui, None))
    for state_key, fallback in (
        ("pick", "Picks only"),
        ("reject", "Rejects only"),
        ("unflagged", "Unflagged only"),
    ):
        a = cull_menu.addAction(lang.get(f"filter_cull_{state_key}", fallback))
        a.triggered.connect(lambda checked, s=state_key: _apply_cull_filter(ui, s))

    # ===== Stack RAW+JPEG =====
    stack_action = filter_menu.addAction(
        lang.get("filter_stack_raw_jpeg", "Stack RAW+JPEG pairs"))
    stack_action.setCheckable(True)
    stack_action.setChecked(bool(user_setting_dict.get("stack_raw_jpeg_pairs")))
    stack_action.toggled.connect(lambda checked: _toggle_stack_mode(ui, checked))

    # ===== 清除篩選 =====
    clear_action = filter_menu.addAction(lang.get("filter_clear", "Clear Filter"))
    clear_action.triggered.connect(lambda: _clear_filter(ui))

    ui._filter_menu = filter_menu
    return filter_menu


def _apply_color_filter(ui: ImervueMainWindow, color: str | None):
    """Filter the tile grid to images matching ``color`` (or clear if None)."""
    from Imervue.user_settings.color_labels import filter_by_color
    viewer = ui.viewer
    all_images = _get_full_image_list(viewer)
    if not all_images:
        return
    filtered = filter_by_color(all_images, color)
    if not filtered:
        return
    viewer.clear_tile_grid()
    viewer.load_tile_grid_async(filtered)


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


def _apply_cull_filter(ui: ImervueMainWindow, state: str | None):
    from Imervue.library import image_index
    viewer = ui.viewer
    all_images = _get_full_image_list(viewer)
    if not all_images:
        return
    filtered = image_index.filter_by_cull(all_images, state) if state else all_images
    if not filtered:
        return
    viewer._unfiltered_images = list(all_images)
    viewer.clear_tile_grid()
    viewer.load_tile_grid_async(filtered)


def _open_advanced(ui: ImervueMainWindow):
    from Imervue.gui.advanced_filter_dialog import open_advanced_filter
    open_advanced_filter(ui)


def _open_multi_tag(ui: ImervueMainWindow):
    from Imervue.gui.tag_filter_dialog import open_tag_filter_dialog
    open_tag_filter_dialog(ui)


def _clear_filter(ui: ImervueMainWindow):
    viewer = ui.viewer
    all_images = _get_full_image_list(viewer)
    if all_images:
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(all_images)


def _toggle_stack_mode(ui: ImervueMainWindow, enabled: bool) -> None:
    """Persist stack setting and reload current folder so collapse applies."""
    from Imervue.user_settings.user_setting_dict import schedule_save
    user_setting_dict["stack_raw_jpeg_pairs"] = bool(enabled)
    schedule_save()
    folder = user_setting_dict.get("user_last_folder")
    if folder and Path(folder).is_dir():
        from Imervue.gpu_image_view.images.image_loader import open_path
        open_path(main_gui=ui.viewer, path=str(folder))


def _get_full_image_list(viewer) -> list[str]:
    """取得完整的圖片列表（未篩選前的）"""
    if hasattr(viewer, '_unfiltered_images') and viewer._unfiltered_images:
        return list(viewer._unfiltered_images)
    return list(viewer.model.images)


def _build_tag_filter(ui: ImervueMainWindow, menu):
    from Imervue.user_settings.tags import get_all_tags
    tags = get_all_tags()
    if not tags:
        lang = language_wrapper.language_word_dict
        action = menu.addAction(lang.get("filter_no_tags", "(No tags)"))
        action.setEnabled(False)
        return
    for tag_name in sorted(tags.keys()):
        count = len(tags[tag_name])
        action = menu.addAction(f"{tag_name}  ({count})")
        action.triggered.connect(
            lambda checked, t=tag_name: _apply_tag_filter(ui, t))


def _apply_tag_filter(ui: ImervueMainWindow, tag_name: str):
    from Imervue.user_settings.tags import get_all_tags
    from pathlib import Path
    tags = get_all_tags()
    images = [p for p in tags.get(tag_name, []) if Path(p).is_file()]
    if not images:
        return
    viewer = ui.viewer
    viewer.clear_tile_grid()
    viewer.load_tile_grid_async(images)


def _build_album_filter(ui: ImervueMainWindow, menu):
    from Imervue.user_settings.tags import get_all_albums
    albums = get_all_albums()
    if not albums:
        lang = language_wrapper.language_word_dict
        action = menu.addAction(lang.get("filter_no_albums", "(No albums)"))
        action.setEnabled(False)
        return
    for album_name in sorted(albums.keys()):
        count = len(albums[album_name])
        action = menu.addAction(f"{album_name}  ({count})")
        action.triggered.connect(
            lambda checked, a=album_name: _apply_album_filter(ui, a))


def _apply_album_filter(ui: ImervueMainWindow, album_name: str):
    from Imervue.user_settings.tags import get_album_images
    from pathlib import Path
    images = [p for p in get_album_images(album_name) if Path(p).is_file()]
    if not images:
        return
    viewer = ui.viewer
    viewer.clear_tile_grid()
    viewer.load_tile_grid_async(images)
