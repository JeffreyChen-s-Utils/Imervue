from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QMenu, QApplication, QWidgetAction

from Imervue.gpu_image_view.actions.batch_ops import (
    open_batch_rename, open_batch_move, batch_rotate,
)
from Imervue.gpu_image_view.actions.compare_dialog import open_compare_dialog
from Imervue.gui.modify_actions_widget import ModifyActionsWidget
from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
from Imervue.gpu_image_view.actions.slideshow import open_slideshow_dialog
from Imervue.gui.export_dialog import open_export_dialog
from Imervue.gui.batch_export_dialog import open_batch_export
from Imervue.gui.gif_video_dialog import open_gif_video_dialog
from Imervue.gui.tag_album_dialog import (
    build_tag_submenu, build_album_submenu, build_batch_tag_album_submenu,
)
from Imervue.gpu_image_view.actions.keyboard_actions import (
    trash_current_image, trash_selected_tiles,
    copy_image_to_clipboard,
)
from Imervue.gpu_image_view.actions.select import switch_to_previous_image, switch_to_next_image
from Imervue.image.info import get_image_info_at_pos, show_image_info_dialog
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.menu.recent_menu import build_recent_menu

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def right_click_context_menu(main_gui: GPUImageView, global_pos, local_pos):
    build_right_click_menu = QMenu(main_gui)

    go_to_parent_folder_action(main_gui=main_gui, menu=build_right_click_menu)
    switch_actions(main_gui=main_gui, menu=build_right_click_menu)

    build_right_click_menu.addSeparator()

    # === 新增快速操作 ===
    _show_in_explorer_action(main_gui, build_right_click_menu)
    _copy_path_action(main_gui, build_right_click_menu)
    _copy_image_action(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _modify_submenu(main_gui, build_right_click_menu)
    _batch_actions(main_gui, build_right_click_menu)
    _delete_action(main_gui, build_right_click_menu)
    _set_wallpaper_action(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _compare_action(main_gui, build_right_click_menu)
    _slideshow_action(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _export_action(main_gui, build_right_click_menu)
    _lossless_rotate_actions(main_gui, build_right_click_menu)
    _batch_convert_action(main_gui, build_right_click_menu)
    _ai_upscale_action(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _bookmark_action(main_gui, build_right_click_menu)
    _tag_album_actions(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    image_info_action(main_gui=main_gui, local_pos=local_pos, menu=build_right_click_menu)
    build_recent_menu(main_gui.main_window, build_right_click_menu)

    # Plugin hook: context menu
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_build_context_menu(build_right_click_menu, main_gui)

    if build_right_click_menu.actions():
        build_right_click_menu.exec(global_pos)


# ===========================
# 取得目前圖片路徑
# ===========================

def _current_image_path(main_gui: GPUImageView) -> str | None:
    images = main_gui.model.images
    if not images:
        return None
    if main_gui.deep_zoom and 0 <= main_gui.current_index < len(images):
        return images[main_gui.current_index]
    return None


# ===========================
# 在檔案總管顯示
# ===========================

def _show_in_explorer_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return

    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_show_in_explorer", "Show in Explorer"))
    action.triggered.connect(lambda: _open_in_explorer(path))


def _open_in_explorer(path: str):
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", str(Path(path).parent)])
    except Exception:
        pass


# ===========================
# 複製路徑
# ===========================

def _copy_path_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return

    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_copy_path", "Copy Path"))
    def _do_copy_path():
        QApplication.clipboard().setText(path)
        if hasattr(main_gui.main_window, "toast"):
            main_gui.main_window.toast.info(
                language_wrapper.language_word_dict.get("toast_path_copied", "Path copied")
            )
    action.triggered.connect(_do_copy_path)


# ===========================
# 複製圖片
# ===========================

def _copy_image_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.deep_zoom:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_copy_image", "Copy Image"))
    action.triggered.connect(lambda: copy_image_to_clipboard(main_gui))


# ===========================
# 修改 — 與主選單 Modify 共用 ModifyActionsWidget
# ===========================

def _modify_submenu(main_gui: GPUImageView, menu: QMenu):
    """Add a "Modify" submenu whose single item is the shared
    :class:`ModifyActionsWidget` — same buttons (Develop / Annotate /
    Rotate CW/CCW / Flip H/V / Reset) as the menu-bar Modify menu.
    """
    if not main_gui.deep_zoom:
        return

    lang = language_wrapper.language_word_dict
    submenu = menu.addMenu(lang.get("modify_menu_title", "Modify"))
    widget_action = QWidgetAction(submenu)
    widget = ModifyActionsWidget(
        main_gui=main_gui,
        parent=submenu,
        on_triggered=menu.close,
    )
    widget_action.setDefaultWidget(widget)
    submenu.addAction(widget_action)


# ===========================
# 刪除（移至垃圾桶）
# ===========================

def _batch_actions(main_gui: GPUImageView, menu: QMenu):
    if not (main_gui.tile_grid_mode and main_gui.tile_selection_mode and main_gui.selected_tiles):
        return
    lang = language_wrapper.language_word_dict
    batch_menu = menu.addMenu(lang.get("right_click_batch", "Batch Operations"))

    rename_action = batch_menu.addAction(lang.get("batch_rename_title", "Batch Rename"))
    rename_action.triggered.connect(lambda: open_batch_rename(main_gui))

    move_action = batch_menu.addAction(lang.get("batch_move_title", "Move / Copy"))
    move_action.triggered.connect(lambda: open_batch_move(main_gui))

    rot_cw = batch_menu.addAction(lang.get("batch_rotate_cw", "Rotate All CW"))
    rot_cw.triggered.connect(lambda: batch_rotate(main_gui, list(main_gui.selected_tiles), 90))

    rot_ccw = batch_menu.addAction(lang.get("batch_rotate_ccw", "Rotate All CCW"))
    rot_ccw.triggered.connect(lambda: batch_rotate(main_gui, list(main_gui.selected_tiles), -90))

    batch_menu.addSeparator()

    export_action = batch_menu.addAction(lang.get("batch_export_title", "Batch Export"))
    export_action.triggered.connect(lambda: open_batch_export(main_gui))

    gif_action = batch_menu.addAction(lang.get("gif_video_title", "Create GIF / Video"))
    gif_action.triggered.connect(lambda: open_gif_video_dialog(main_gui))

    build_batch_tag_album_submenu(main_gui, list(main_gui.selected_tiles), batch_menu)


def _delete_action(main_gui: GPUImageView, menu: QMenu):
    lang = language_wrapper.language_word_dict

    if main_gui.tile_grid_mode and main_gui.tile_selection_mode:
        action = menu.addAction(lang.get("right_click_menu_delete_selected"))
        action.triggered.connect(lambda: trash_selected_tiles(main_gui))

    if main_gui.deep_zoom:
        action = menu.addAction(lang.get("right_click_menu_delete_current"))
        action.triggered.connect(lambda: trash_current_image(main_gui))


# ===========================
# 設為桌布
# ===========================

def _set_wallpaper_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return

    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_set_wallpaper", "Set as Wallpaper"))
    action.triggered.connect(lambda: _set_wallpaper(path))


def _set_wallpaper(path: str):
    try:
        if sys.platform == "win32":
            import ctypes
            SPI_SETDESKWALLPAPER = 0x0014
            SPIF_UPDATEINIFILE = 0x01
            SPIF_SENDCHANGE = 0x02
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 0, os.path.normpath(path),
                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            )
        elif sys.platform == "darwin":
            script = f'''
            tell application "Finder"
                set desktop picture to POSIX file "{path}"
            end tell
            '''
            subprocess.Popen(["osascript", "-e", script])
        else:
            # GNOME
            subprocess.Popen([
                "gsettings", "set", "org.gnome.desktop.background",
                "picture-uri", f"file://{path}"
            ])
    except Exception:
        pass


# ===========================
# 原有功能
# ===========================

def _slideshow_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.model.images or len(main_gui.model.images) < 2:
        return
    lang = language_wrapper.language_word_dict

    if hasattr(main_gui, '_slideshow') and main_gui._slideshow and main_gui._slideshow.running:
        action = menu.addAction(lang.get("right_click_slideshow_stop", "Stop Slideshow"))
        action.triggered.connect(lambda: main_gui._slideshow.stop())
    else:
        action = menu.addAction(lang.get("right_click_slideshow", "Slideshow"))
        action.triggered.connect(lambda: open_slideshow_dialog(main_gui))


def _compare_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.model.images or len(main_gui.model.images) < 2:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_compare", "Compare Images"))
    action.triggered.connect(lambda: open_compare_dialog(main_gui))


def switch_actions(main_gui: GPUImageView, menu: QMenu):
    if main_gui.deep_zoom:
        next_image_action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_next_image"))
        next_image_action.triggered.connect(
            lambda: switch_to_next_image(main_gui=main_gui)
        )
        previous_image_action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_previous_image")
        )
        previous_image_action.triggered.connect(
            lambda: switch_to_previous_image(main_gui=main_gui)
        )


def go_to_parent_folder_action(main_gui: GPUImageView, menu: QMenu):
    images = main_gui.model.images
    if images:
        current_path = None
        if main_gui.deep_zoom and 0 <= main_gui.current_index < len(images):
            current_path = images[main_gui.current_index]
        elif main_gui.tile_grid_mode:
            current_path = images[0]

        if current_path:
            parent_folder = Path(current_path).parent.parent

            if parent_folder.exists():
                action = menu.addAction(
                    language_wrapper.language_word_dict.get("right_click_menu_go_to_parent_folder"))
                action.triggered.connect(
                    lambda: jump_to_folder(main_gui=main_gui, folder_path=parent_folder)
                )


def jump_to_folder(main_gui: GPUImageView, folder_path: Path):
    model = main_gui.main_window.model
    tree = main_gui.main_window.tree

    index = model.index(str(folder_path))
    if index.isValid():
        tree.setCurrentIndex(index)
        tree.scrollTo(index)
        tree.setRootIndex(index)


def image_info_action(main_gui: GPUImageView, local_pos, menu: QMenu):
    info = get_image_info_at_pos(main_gui=main_gui, position=local_pos)
    if info:
        action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_image_info")
        )
        action.triggered.connect(
            lambda: image_info(main_gui=main_gui, info=info)
        )


def image_info(main_gui: GPUImageView, info):
    show_image_info_dialog(main_gui=main_gui, info=info)


# ===========================
# 匯出 / 另存為
# ===========================

def _export_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_export", "Export / Save As..."))
    action.triggered.connect(lambda: open_export_dialog(main_gui))


# ===========================
# 無損旋轉
# ===========================

def _lossless_rotate_actions(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return
    lang = language_wrapper.language_word_dict
    sub = menu.addMenu(lang.get("right_click_lossless_rotate", "Lossless Rotate"))

    cw = sub.addAction(lang.get("lossless_rotate_cw", "Lossless Rotate CW"))
    cw.triggered.connect(lambda: _do_lossless_rotate(main_gui, path, clockwise=True))

    ccw = sub.addAction(lang.get("lossless_rotate_ccw", "Lossless Rotate CCW"))
    ccw.triggered.connect(lambda: _do_lossless_rotate(main_gui, path, clockwise=False))


def _bookmark_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return
    lang = language_wrapper.language_word_dict
    from Imervue.user_settings.bookmark import is_bookmarked
    if is_bookmarked(path):
        action = menu.addAction(lang.get("bookmark_remove_current", "Remove Bookmark"))
    else:
        action = menu.addAction(lang.get("bookmark_add_current", "Add Bookmark"))
    action.triggered.connect(lambda: main_gui._toggle_bookmark())


def _tag_album_actions(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return
    build_tag_submenu(main_gui, path, menu)
    build_album_submenu(main_gui, path, menu)


def _do_lossless_rotate(main_gui: GPUImageView, path: str, clockwise: bool):
    lang = language_wrapper.language_word_dict
    ok = lossless_rotate(path, clockwise=clockwise)
    if ok:
        if hasattr(main_gui.main_window, "toast"):
            main_gui.main_window.toast.info(
                lang.get("lossless_rotate_done", "Lossless rotation saved!")
            )
        # 重新載入圖片以反映旋轉
        from Imervue.gpu_image_view.images.image_loader import open_path
        main_gui._clear_deep_zoom()
        open_path(main_gui=main_gui, path=path)
    else:
        if hasattr(main_gui.main_window, "toast"):
            main_gui.main_window.toast.info(
                lang.get("lossless_rotate_fail", "Lossless rotation failed")
            )


# ===========================
# 批次格式轉換
# ===========================

def _batch_convert_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.model.images:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(
        lang.get("batch_convert_title", "Batch Format Conversion"))
    action.triggered.connect(lambda: _do_batch_convert(main_gui))


def _do_batch_convert(main_gui: GPUImageView):
    from Imervue.gui.batch_convert_dialog import open_batch_convert
    open_batch_convert(main_gui)


# ===========================
# AI 圖片放大
# ===========================

def _ai_upscale_action(main_gui: GPUImageView, menu: QMenu):
    lang = language_wrapper.language_word_dict
    # Single image in deep zoom
    if main_gui.deep_zoom:
        images = main_gui.model.images
        if images and 0 <= main_gui.current_index < len(images):
            path = images[main_gui.current_index]
            action = menu.addAction(
                lang.get("upscale_quick", "AI Upscale — Current Image"))
            action.triggered.connect(
                lambda: _do_upscale_single(main_gui, path))
    # Batch in tile selection
    if (main_gui.tile_grid_mode and main_gui.tile_selection_mode
            and main_gui.selected_tiles):
        action = menu.addAction(
            lang.get("upscale_batch", "AI Upscale — Selected Images"))
        action.triggered.connect(lambda: _do_upscale_batch(main_gui))


def _do_upscale_single(main_gui: GPUImageView, path: str):
    from Imervue.gui.ai_upscale_dialog import open_ai_upscale_single
    open_ai_upscale_single(main_gui, path)


def _do_upscale_batch(main_gui: GPUImageView):
    from Imervue.gui.ai_upscale_dialog import open_ai_upscale_batch
    open_ai_upscale_batch(main_gui)
