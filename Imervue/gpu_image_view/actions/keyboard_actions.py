"""
鍵盤快捷鍵動作
Keyboard shortcut actions for GPUImageView.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QClipboard
from PySide6.QtWidgets import QApplication

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


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


def trash_current_image(main_gui: GPUImageView) -> bool:
    """將目前 DeepZoom 顯示的圖片移至系統垃圾桶，成功回傳 True"""
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return False

    path = images[main_gui.current_index]
    if not _send_to_trash(path):
        _toast(main_gui, f"Failed to trash: {Path(path).name}", "error")
        return False

    deleted_index = main_gui.current_index
    images.pop(deleted_index)

    # Plugin hook
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_image_deleted([path], main_gui)

    # GPU cleanup
    from OpenGL.GL import glDeleteTextures
    tex = main_gui.tile_textures.pop(path, None)
    if tex is not None:
        glDeleteTextures([tex])

    if images:
        main_gui.current_index = min(deleted_index, len(images) - 1)
        main_gui.load_deep_zoom_image(images[main_gui.current_index])
    else:
        main_gui.deep_zoom = None
        main_gui.current_index = 0
        main_gui.tile_grid_mode = True

    main_gui.update()
    return True


def trash_selected_tiles(main_gui: GPUImageView) -> bool:
    """將選取的縮圖移至系統垃圾桶"""
    paths = list(main_gui.selected_tiles)
    if not paths:
        return False

    images = main_gui.model.images
    items_to_delete = []
    for path in paths:
        if path in images and _send_to_trash(path):
            idx = images.index(path)
            items_to_delete.append((path, idx))

    if not items_to_delete:
        return False

    from OpenGL.GL import glDeleteTextures
    for path, idx in sorted(items_to_delete, key=lambda x: x[1], reverse=True):
        images.pop(idx)
        tex = main_gui.tile_textures.pop(path, None)
        if tex is not None:
            glDeleteTextures([tex])
        main_gui.tile_cache.pop(path, None)

    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_image_deleted(
            [p for p, _ in items_to_delete], main_gui
        )

    main_gui.selected_tiles.clear()
    main_gui.tile_selection_mode = False
    main_gui.tile_rects.clear()
    main_gui.update()
    return True


def _send_to_trash(path: str) -> bool:
    """嘗試將檔案移至系統垃圾桶，回傳是否成功"""
    try:
        from send2trash import send2trash
        send2trash(path)
        return True
    except ImportError:
        pass

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
            dest = trash_dir / Path(path).name
            # 避免覆蓋：加時間戳
            if dest.exists():
                import time
                stem = dest.stem
                dest = trash_dir / f"{stem}_{int(time.time())}{dest.suffix}"
            shutil.move(path, str(dest))
            return True
        else:
            # Linux: freedesktop.org Trash spec
            import shutil, time, os as _os
            uid = _os.getuid()
            # 判斷是否在同一個 mount point
            home_trash = Path.home() / ".local" / "share" / "Trash"
            files_dir = home_trash / "files"
            info_dir = home_trash / "info"
            files_dir.mkdir(parents=True, exist_ok=True)
            info_dir.mkdir(parents=True, exist_ok=True)

            base_name = Path(path).name
            dest = files_dir / base_name
            # 避免覆蓋
            if dest.exists():
                stem = Path(path).stem
                ext = Path(path).suffix
                dest = files_dir / f"{stem}_{int(time.time())}{ext}"
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
    except Exception:
        return False


# ===========================
# R / Shift+R — 旋轉
# ===========================

def rotate_current_image(main_gui: GPUImageView, clockwise: bool = True):
    """旋轉目前 DeepZoom 金字塔（記憶體內旋轉，不修改原始檔案）"""
    import numpy as np
    dz = main_gui.deep_zoom
    if dz is None:
        return

    k = 3 if clockwise else 1  # np.rot90 逆時針，k=3 = 順時針 90°
    for i in range(len(dz.levels)):
        dz.levels[i] = np.rot90(dz.levels[i], k=k)

    # 重建 TileManager（清除舊的 GPU tile cache）
    from Imervue.image.tile_manager import TileManager
    if main_gui.tile_manager is not None:
        main_gui.tile_manager.clear()
    main_gui.tile_manager = TileManager(dz)

    # 重新 fit-to-window（旋轉後尺寸可能改變）
    main_gui._fit_to_window()
    main_gui.update()


# ===========================
# Ctrl+C — 複製到剪貼簿
# ===========================

def copy_image_to_clipboard(main_gui: GPUImageView):
    """複製當前圖片到系統剪貼簿"""
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return

    path = images[main_gui.current_index]
    try:
        qimg = QImage(path)
        if qimg.isNull() and main_gui.deep_zoom is not None:
            # QImage 無法直接載入（例如 SVG），從 deep zoom 金字塔取得
            import numpy as np
            data = main_gui.deep_zoom.levels[0]
            h, w = data.shape[:2]
            ch = data.shape[2] if data.ndim == 3 else 1
            if ch == 4:
                # RGBA → BGRA for QImage
                bgra = data.copy()
                bgra[:, :, [0, 2]] = bgra[:, :, [2, 0]]
                qimg = QImage(bgra.data, w, h, w * 4, QImage.Format.Format_ARGB32)
                qimg = qimg.copy()  # 脫離 numpy buffer
            elif ch == 3:
                rgb = np.ascontiguousarray(data)
                qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
                qimg = qimg.copy()
        if not qimg.isNull():
            clipboard = QApplication.clipboard()
            clipboard.setImage(qimg)
    except Exception:
        pass


# ===========================
# 1~5 — 快速評分標記
# ===========================

def rate_current_image(main_gui: GPUImageView, rating: int):
    """為當前圖片設定 1~5 評分（存入 user_setting）"""
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return

    path = images[main_gui.current_index]

    from Imervue.user_settings.user_setting_dict import user_setting_dict
    ratings = user_setting_dict.get("image_ratings", {})

    current = ratings.get(path)
    if current == rating:
        # 相同評分 → 取消
        ratings.pop(path, None)
    else:
        ratings[path] = rating

    user_setting_dict["image_ratings"] = ratings

    # 通知 UI 更新
    from Imervue.multi_language.language_wrapper import language_wrapper
    lang = language_wrapper.language_word_dict
    if path in ratings:
        star = "\u2605" * ratings[path]
        msg = lang.get("rating_set", "Rating: {star}").format(star=star)
    else:
        msg = lang.get("rating_cleared", "Rating cleared")

    _show_status(main_gui, msg)


# ===========================
# 0 — 愛心收藏
# ===========================

def toggle_favorite(main_gui: GPUImageView):
    """切換愛心收藏狀態"""
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return

    path = images[main_gui.current_index]

    from Imervue.user_settings.user_setting_dict import user_setting_dict
    favorites = set(user_setting_dict.get("image_favorites", []))

    if path in favorites:
        favorites.discard(path)
    else:
        favorites.add(path)

    user_setting_dict["image_favorites"] = list(favorites)

    from Imervue.multi_language.language_wrapper import language_wrapper
    lang = language_wrapper.language_word_dict
    if path in favorites:
        msg = lang.get("favorite_added", "\u2764 Favorited")
    else:
        msg = lang.get("favorite_removed", "Favorite removed")

    _show_status(main_gui, msg)


def _show_status(main_gui: GPUImageView, text: str):
    """在 filename_label 短暫顯示狀態訊息"""
    win = main_gui.main_window
    if hasattr(win, "filename_label"):
        original = win.filename_label.text()
        win.filename_label.setText(text)

        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: win.filename_label.setText(original))
