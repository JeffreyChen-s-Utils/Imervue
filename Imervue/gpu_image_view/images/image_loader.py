from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QRunnable, Signal, QObject

from Imervue.image.pyramid import DeepZoomImage

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

import imageio
import numpy as np
import rawpy
from PIL import Image

logger = logging.getLogger("Imervue.image_loader")


def _maybe_collapse_stacks(images: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Collapse RAW+JPEG pairs when the user has the setting enabled."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    if not user_setting_dict.get("stack_raw_jpeg_pairs"):
        return list(images), {}
    from Imervue.library.stacks import collapse_stacks
    return collapse_stacks(list(images))


_RAW_EXTS = frozenset({".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"})


def _load_raw(path: str, thumbnail: bool) -> np.ndarray:
    with rawpy.imread(path) as raw:
        if thumbnail:
            return _load_raw_thumbnail(raw)
        return raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=False,
            output_bps=8,
        )


def _load_raw_thumbnail(raw) -> np.ndarray:
    try:
        thumb = raw.extract_thumb()
        if thumb.format == rawpy.ThumbFormat.JPEG:
            return imageio.v3.imread(thumb.data)
        if thumb.format == rawpy.ThumbFormat.BITMAP:
            return thumb.data
        raise ValueError("No valid embedded preview")
    except (ValueError, OSError, RuntimeError):
        return raw.postprocess(
            half_size=True,
            use_camera_wb=True,
            output_bps=8,
        )


def _load_raster(path: str) -> np.ndarray:
    img = Image.open(path)
    # 避免不必要的 RGBA 轉換 — 原生 RGB/L 交給下方補 alpha 的共用路徑處理.
    # 省掉一次全圖的記憶體複製. 60 MP+ JPEG 記憶體峰值約少 25%.
    # Palette/CMYK 等怪模式仍走 convert("RGBA") 避免 numpy 解讀錯誤.
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGBA")
    return np.array(img)


def _ensure_rgba(img_data: np.ndarray) -> np.ndarray:
    if img_data.ndim == 2:
        img_data = np.stack([img_data, img_data, img_data], axis=2)
    if img_data.shape[2] == 3:
        alpha = np.ones((*img_data.shape[:2], 1), dtype=np.uint8) * 255
        img_data = np.concatenate([img_data, alpha], axis=2)
    return img_data


def load_image_file(path, thumbnail=False, recipe=None):
    """
    支援一般圖片 + RAW 檔案
    thumbnail=True 時會優先使用 RAW embedded preview 或 half_size
    回傳 numpy RGBA

    ``recipe`` 是可選的 :class:`Imervue.image.recipe.Recipe`: 若提供, 非 identity
    的部分會在回傳前套到 RGBA 陣列上. 呼叫端也可以先自行查 recipe_store 再決定
    要不要傳進來, 這個函式不強制依賴 store.
    """
    ext = Path(path).suffix.lower()
    if ext in _RAW_EXTS:
        img_data = _load_raw(path, thumbnail)
    elif ext == ".svg":
        img_data = _load_svg(path, thumbnail=thumbnail)
    else:
        img_data = _load_raster(path)

    img_data = _ensure_rgba(img_data)

    if recipe is not None and not recipe.is_identity():
        try:
            img_data = recipe.apply(img_data)
        except Exception as exc:  # noqa: BLE001
            # 一張圖片的 recipe 壞掉不該害整個載入流程炸掉; log 一下繼續用
            # 原始像素. 使用者下一次打開 Develop panel 會看到 reset 過的值.
            logger.warning(f"Recipe apply failed for {path}: {exc}")

    return img_data


# ================================================================
# DeepZoom 非同步載入 Worker
# ================================================================

class _DeepZoomWorkerSignals(QObject):
    finished = Signal(object, str)  # (DeepZoomImage, path)


class LoadDeepZoomWorker(QRunnable):
    """在背景執行緒載入全解析度圖片並建立金字塔，避免凍結 UI"""

    def __init__(self, path: str, recipe=None):
        super().__init__()
        self.path = path
        self.recipe = recipe
        self.signals = _DeepZoomWorkerSignals()
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        if self._abort:
            return
        try:
            img_data = load_image_file(self.path, thumbnail=False, recipe=self.recipe)
            if self._abort:
                return
            dzi = DeepZoomImage(img_data)
            del img_data  # 釋放原始圖片記憶體，金字塔已持有降採樣副本
            if not self._abort:
                self.signals.finished.emit(dzi, self.path)
        except Exception as e:
            logger.error(f"DeepZoom load failed: {self.path} - {e}")


# ================================================================
# 開啟路徑（資料夾或檔案）
# ================================================================

_SUPPORTED_EXTS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
    ".gif", ".apng", ".svg",
    ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf",
}


def _load_svg(path: str, thumbnail: bool = False) -> np.ndarray:
    """Render SVG to RGBA numpy array using QSvgRenderer."""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtCore import Qt, QSize

    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        raise ValueError(f"Invalid SVG file: {path}")

    size = renderer.defaultSize()
    if size.isEmpty():
        size = QSize(1024, 1024)

    if thumbnail:
        # Scale down for thumbnail
        max_dim = 512
        if size.width() > max_dim or size.height() > max_dim:
            size.scale(max_dim, max_dim, Qt.AspectRatioMode.KeepAspectRatio)

    img = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()

    # QImage → numpy (BGRA → RGBA)
    w, h = img.width(), img.height()
    ptr = img.bits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 4)).copy()
    # BGRA → RGBA
    arr[:, :, [0, 2]] = arr[:, :, [2, 0]]
    return arr


def _scan_images(directory: str, sort_by: str = "name", ascending: bool = True) -> list[str]:
    """
    快速掃描資料夾中的圖片，直接用使用者選定的排序方式一次排完（不再先 sort by name 再 re-sort）。
    Default arguments preserve the historical behaviour (alphabetical ascending)
    so external callers that don't care about user settings — the main window's
    folder refresh and the unit tests — keep getting the same result.
    """
    import os
    result = []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False):
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in _SUPPORTED_EXTS:
                        result.append(entry.path)
    except OSError:
        return []

    if sort_by == "name":
        # Fast default path — avoid the import of sort_menu for the common case.
        result.sort(key=lambda p: os.path.basename(p).lower(), reverse=not ascending)
    else:
        from Imervue.menu.sort_menu import _SORT_KEYS, _sort_key_name
        key_fn = _SORT_KEYS.get(sort_by, _sort_key_name)
        result.sort(key=key_fn, reverse=not ascending)
    return result


def _scan_images_for_user(directory: str) -> list[str]:
    """Scan + sort a folder using the user's current sort settings (single pass)."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    return _scan_images(
        directory,
        sort_by=user_setting_dict.get("sort_by", "name"),
        ascending=user_setting_dict.get("sort_ascending", True),
    )


def open_path(main_gui: GPUImageView, path: str):
    path_obj = Path(path)
    if path_obj.is_dir():
        _open_folder(main_gui, path_obj)
    elif path_obj.is_file() and path_obj.suffix.lower() in _SUPPORTED_EXTS:
        _open_file(main_gui, path_obj)


def _open_folder(main_gui: GPUImageView, path_obj: Path) -> None:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    from Imervue.user_settings.recent_image import add_recent_folder
    images = _scan_images_for_user(str(path_obj))
    if not images:
        return
    main_gui.current_index = 0
    main_gui._unfiltered_images = list(images)
    images, stacks = _maybe_collapse_stacks(images)
    main_gui._stack_members = stacks
    main_gui.load_tile_grid_async(images)
    add_recent_folder(str(path_obj))
    user_setting_dict["user_last_folder"] = str(path_obj)
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_folder_opened(
            str(path_obj), images, main_gui,
        )


def _open_file(main_gui: GPUImageView, path_obj: Path) -> None:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    from Imervue.user_settings.recent_image import add_recent_image
    dir_path = path_obj.parent
    images = _scan_images_for_user(str(dir_path))
    if not images:
        return
    main_gui._unfiltered_images = list(images)
    images, stacks = _maybe_collapse_stacks(images)
    main_gui._stack_members = stacks
    main_gui.model.set_images(images)
    main_gui.current_index = _locate_current_index(images, str(path_obj))
    main_gui.tile_grid_mode = False
    main_gui.load_deep_zoom_image(str(path_obj))
    add_recent_image(str(path_obj))
    user_setting_dict["user_last_folder"] = str(dir_path)
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_image_loaded(str(path_obj), main_gui)


def _locate_current_index(images: list[str], target: str) -> int:
    try:
        return images.index(target)
    except ValueError:
        import os
        norm = os.path.normpath(target)
        for i, p in enumerate(images):
            if os.path.normpath(p) == norm:
                return i
        return 0
