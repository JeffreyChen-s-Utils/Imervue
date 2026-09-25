"""
鍵盤快捷鍵動作
Keyboard shortcut actions for GPUImageView.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from Imervue.system.best_effort import best_effort

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.keyboard_actions")


# ===========================
# F — 全螢幕切換
# ===========================

def toggle_fullscreen(main_gui: GPUImageView):
    win = main_gui.main_window
    if win.isFullScreen():
        # 還原到先前儲存的視窗狀態，避免 showNormal→showMaximized 閃爍
        if getattr(win, '_was_maximized_before_fs', False):
            win.showMaximized()
        else:
            win.showNormal()
    else:
        win._was_maximized_before_fs = win.isMaximized()
        win.showFullScreen()


# ===========================
# Delete — 移至垃圾桶
# ===========================

def _toast(main_gui: GPUImageView, text: str, level: str = "info"):
    """安全地顯示 toast 通知"""
    win = main_gui.main_window
    if hasattr(win, "toast"):
        getattr(win.toast, level, win.toast.info)(text)


def _free_trash_name(files_dir: Path, name: str, info_dir: Path | None = None) -> Path:
    """First of ``name``, ``stem_1.ext``, ``stem_2.ext`` … not taken in *files_dir*.

    With *info_dir* (freedesktop trash) the name must also have no
    ``.trashinfo`` there. A timestamp suffix used to collide when two files of
    the same name were trashed within one second, and the move overwrote the
    earlier one.
    """
    stem, suffix = Path(name).stem, Path(name).suffix
    candidate, counter = name, 1
    while (files_dir / candidate).exists() or (
            info_dir is not None and (info_dir / f"{candidate}.trashinfo").exists()):
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    return files_dir / candidate


def _send_to_trash(path: str) -> bool:
    """嘗試將檔案移至系統垃圾桶，回傳是否成功"""
    try:
        from send2trash import send2trash
        send2trash(path)
        return True
    except ImportError:
        pass
    except OSError:
        # A locked or vanished file: raising here ended the whole batch it was
        # retried from, reporting files already trashed as failed.
        logger.warning("Couldn't send %s to the trash", path, exc_info=True)
        return False

    # fallback: 使用平台原生方式
    try:
        import sys
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            # SHFileOperationW with FOF_ALLOWUNDO
            class SHFILEOPSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", ctypes.c_uint),
                    ("pFrom", ctypes.c_wchar_p),
                    ("pTo", ctypes.c_wchar_p),
                    ("fFlags", ctypes.c_ushort),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", ctypes.c_wchar_p),
                ]
            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_SILENT = 0x0004
            op = SHFILEOPSTRUCT()
            op.wFunc = FO_DELETE
            op.pFrom = path + "\0"
            op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
            result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
            return result == 0
        elif sys.platform == "darwin":
            # macOS: move to ~/.Trash/
            import shutil
            trash_dir = Path.home() / ".Trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            dest = _free_trash_name(trash_dir, Path(path).name)
            shutil.move(path, str(dest))
            return True
        else:
            # Linux: freedesktop.org Trash spec
            import shutil
            # 判斷是否在同一個 mount point
            home_trash = Path.home() / ".local" / "share" / "Trash"
            files_dir = home_trash / "files"
            info_dir = home_trash / "info"
            files_dir.mkdir(parents=True, exist_ok=True)
            info_dir.mkdir(parents=True, exist_ok=True)

            dest = _free_trash_name(files_dir, Path(path).name, info_dir)
            base_name = dest.name

            # 寫入 .trashinfo
            from datetime import datetime
            info_content = (
                "[Trash Info]\n"
                f"Path={path}\n"
                f"DeletionDate={datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n"
            )
            info_file = info_dir / f"{base_name}.trashinfo"
            info_file.write_text(info_content, encoding="utf-8")

            shutil.move(path, str(dest))
            return True
    except OSError:
        # mkdir / write_text / move (shutil.Error is an OSError) on the fallback path.
        return False


# ===========================
# R / Shift+R — 旋轉
# ===========================

def rotate_current_image(main_gui: GPUImageView, clockwise: bool = True):
    """Rotate the current image via the non-destructive recipe system.

    Previously this walked the DeepZoom pyramid and rotated every level in
    place — fast, but lost the rotation as soon as the user navigated away.
    Now it pushes a rotate onto the image's Recipe so the rotation persists
    across sessions, and reloads the image so the new pixels show up.
    Use the "Lossless Rotate" submenu if you want to actually modify the
    file on disk (truly lossless EXIF rotation for JPEGs).
    """
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return
    path = images[main_gui.current_index]

    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store
    from Imervue.gpu_image_view.actions.recipe_commands import EditRecipeCommand

    old = recipe_store.get_for_path(path) or Recipe()
    new = Recipe.from_dict(old.to_dict())
    delta = 1 if clockwise else -1
    new.rotate_steps = (new.rotate_steps + delta) % 4

    cmd = EditRecipeCommand(main_gui, path, old, new, text="Rotate")
    main_gui.undo_manager.push(cmd)


# ===========================
# Ctrl+C — 複製到剪貼簿
# ===========================

def copy_image_to_clipboard(main_gui: GPUImageView):
    """複製當前圖片到系統剪貼簿"""
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return

    path = images[main_gui.current_index]
    with best_effort("copy the image to the clipboard"):
        qimg = _shown_image(main_gui, path)
        if not qimg.isNull():
            clipboard = QApplication.clipboard()
            clipboard.setImage(qimg)


def _shown_image(main_gui: GPUImageView, path: str) -> QImage:
    """What the viewer shows for *path*: its full-size pyramid level, else a fresh decode.

    The deep-zoom base level carries the develop recipe, the sRGB conversion
    and the EXIF turn; ``QImage(path)`` had none of them (a portrait phone
    photo was pasted sideways) and could not read a RAW or HEIC.
    """
    if main_gui.deep_zoom is not None:
        import numpy as np
        from PIL import Image

        from Imervue.system.qimage_convert import pil_to_qimage
        return pil_to_qimage(Image.fromarray(np.ascontiguousarray(main_gui.deep_zoom.levels[0])))
    from Imervue.gui.shown_qimage import shown_qimage
    return shown_qimage(path)


# ===========================
# 1~5 — 快速評分標記
# ===========================

def rate_current_image(main_gui: GPUImageView, rating: int):
    """Give the photos the key acts on a 1-5 *rating*; when they all have it already, clear it.

    The photos are the ones a colour label or a cull flag would take
    (:func:`~Imervue.gpu_image_view.cull_actions.resolve_cull_targets`): the
    selected tiles, the deep-zoom image, the tile the arrow keys are on, or
    the hovered tile.
    """
    from Imervue.gpu_image_view.cull_actions import resolve_cull_targets
    targets = resolve_cull_targets(main_gui)
    if not targets:
        return

    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save
    ratings = user_setting_dict.get("image_ratings", {})
    result = 0 if all(ratings.get(path) == rating for path in targets) else rating
    for path in targets:
        if result:
            ratings[path] = result
        else:
            ratings.pop(path, None)   # 相同評分 → 取消

    user_setting_dict["image_ratings"] = ratings
    schedule_save()

    # Macro recording — capture the resulting rating (0 means "cleared").
    from Imervue.macros.macro_manager import manager as _macro_manager
    _macro_manager.record("set_rating", rating=result)

    # 通知 UI 更新
    from Imervue.multi_language.language_wrapper import language_wrapper
    lang = language_wrapper.language_word_dict
    if result:
        msg = lang.get("rating_set", "Rating: {star}").format(star="\u2605" * result)
    else:
        msg = lang.get("rating_cleared", "Rating cleared")

    main_gui._quick_meta_hud = (msg, __import__("time").monotonic() + 1.2)
    _show_status(main_gui, msg)


# ===========================
# 0 — 愛心收藏
# ===========================

def toggle_favorite(main_gui: GPUImageView):
    """Favourite the photos the key acts on; when they all are already, unfavourite them.

    The photos are resolved like a rating's (:func:`rate_current_image`).
    """
    from Imervue.gpu_image_view.cull_actions import resolve_cull_targets
    targets = resolve_cull_targets(main_gui)
    if not targets:
        return

    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save
    favorites = set(user_setting_dict.get("image_favorites", []))
    favourite = not all(path in favorites for path in targets)
    if favourite:
        favorites.update(targets)
    else:
        favorites.difference_update(targets)

    user_setting_dict["image_favorites"] = list(favorites)
    schedule_save()

    # Macro recording — record the resulting favorite state.
    from Imervue.macros.macro_manager import manager as _macro_manager
    _macro_manager.record("toggle_favorite", value=favourite)

    from Imervue.multi_language.language_wrapper import language_wrapper
    lang = language_wrapper.language_word_dict
    if favourite:
        msg = lang.get("favorite_added", "\u2764 Favorited")
    else:
        msg = lang.get("favorite_removed", "Favorite removed")

    _show_status(main_gui, msg)


def _show_status(main_gui: GPUImageView, text: str):
    """在 filename_label 短暫顯示狀態訊息，1.5 秒後還原真正的標題。

    Rapid consecutive ratings must not clobber the real caption: a naive
    singleShot captured ``filename_label.text()`` each call, so the second rating
    captured the FIRST rating's transient text as the "original" and restored to
    it, losing the real folder caption. A single reusable timer captures the real
    caption only when no transient is already showing, and always restores it."""
    win = main_gui.main_window
    if not hasattr(win, "filename_label"):
        return
    from PySide6.QtCore import QTimer
    timer = getattr(win, "_status_restore_timer", None)
    if timer is None:
        timer = QTimer(win)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: _restore_caption(win))
        win._status_restore_timer = timer   # noqa: SLF001
    if not timer.isActive():
        # No transient is showing, so the label currently holds the real caption.
        win._status_original_caption = win.filename_label.text()   # noqa: SLF001
    win.filename_label.setText(text)
    timer.start(1500)


def _restore_caption(win) -> None:
    win.filename_label.setText(getattr(win, "_status_original_caption", ""))
