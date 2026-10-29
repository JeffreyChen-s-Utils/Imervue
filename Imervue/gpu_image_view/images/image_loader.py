from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from Imervue.system.pixel_limit import decode_slot
from Imervue.image.formats import RAW_EXTENSIONS, VIEWER_EXTENSIONS, ensure_pillow_opener
from Imervue.image.color_profile import to_srgb
from Imervue.image.high_bit_depth import to_eight_bit
from Imervue.image.orientation import exif_orientation, transpose_for
from Imervue.image.video_frames import VIDEO_EXTENSIONS, poster_frame
from Imervue.gpu_image_view.images.image_loader_deep_zoom import (
    LoadDeepZoomWorker,
    _DeepZoomWorkerSignals,
)
from Imervue.gpu_image_view.images.image_loader_open import (
    _apply_folder_scan_paths,
    _locate_current_index,
    _maybe_collapse_stacks,
    _maybe_hint_heif,
    _on_folder_scan_batch,
    _on_folder_scan_finished,
    _open_file,
    _open_folder,
    _open_folder_progressive,
    cancel_folder_scan,
)
from Imervue.gpu_image_view.images.image_loader_scan import (
    FolderScanWorker,
    _FolderScanSignals,
    _is_listed,
    _scan_images,
    _scan_images_for_user,
    _sort_for_user,
    _stat_value,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

import numpy as np
from PIL import Image

logger = logging.getLogger("Imervue.image_loader")

__all__ = [
    "FolderScanWorker",
    "LoadDeepZoomWorker",
    "_DeepZoomWorkerSignals",
    "_FolderScanSignals",
    "_apply_folder_scan_paths",
    "_ensure_rgba",
    "_is_listed",
    "_load_raster",
    "_load_raster_thumbnail",
    "_load_raw",
    "_load_svg",
    "_locate_current_index",
    "_maybe_collapse_stacks",
    "_maybe_hint_heif",
    "_on_folder_scan_batch",
    "_on_folder_scan_finished",
    "_open_file",
    "_open_folder",
    "_open_folder_progressive",
    "_scan_images",
    "_scan_images_for_user",
    "_sort_for_user",
    "_stat_value",
    "cancel_folder_scan",
    "decode_image",
    "decode_image_file",
    "load_image_file",
    "open_path",
]


_THUMBNAIL_EDGE = 1600   # long side of a thumbnail decode of a raster


def _load_raw(path: str, thumbnail: bool) -> np.ndarray:
    """Develop the camera RAW at *path* (:func:`Imervue.image.raw_loader.develop_raw`)."""
    from Imervue.image.raw_loader import develop_raw
    return develop_raw(path, thumbnail=thumbnail)


def _load_raster(path: str, *, orient: bool = True) -> np.ndarray:
    img = Image.open(path)
    code = exif_orientation(img) if orient else 1
    with decode_slot(img.width * img.height):   # one giant panorama at a time
        img = to_srgb(to_eight_bit(img))   # 16-bit / float grey scaled; profile -> screen sRGB
        # 避免不必要的 RGBA 轉換 — 原生 RGB/L 交給下方補 alpha 的共用路徑處理.
        # 省掉一次全圖的記憶體複製. 60 MP+ JPEG 記憶體峰值約少 25%.
        # Palette/CMYK 等怪模式仍走 convert("RGBA") 避免 numpy 解讀錯誤.
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGBA")
        return np.array(transpose_for(img, code))


def _load_raster_thumbnail(path: str, max_edge: int = _THUMBNAIL_EDGE, *,
                           orient: bool = True) -> np.ndarray:
    with Image.open(path) as img, decode_slot(img.width * img.height):
        code = exif_orientation(img) if orient else 1
        # Past JPEG's draft decode this reads every pixel: a giant waits its turn.
        img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        shown = to_srgb(to_eight_bit(img))   # after the downscale: converting fewer pixels
        thumb = shown.convert("RGBA") if shown.mode not in ("RGB", "RGBA", "L") else shown
        return np.array(transpose_for(thumb, code))


def _ensure_rgba(img_data: np.ndarray) -> np.ndarray:
    if img_data.ndim == 2:
        img_data = np.stack([img_data, img_data, img_data], axis=2)
    if img_data.shape[2] == 3:
        alpha = np.ones((*img_data.shape[:2], 1), dtype=np.uint8) * 255
        img_data = np.concatenate([img_data, alpha], axis=2)
    return img_data


def decode_image_file(path, *, thumbnail: bool = False, orient: bool = True) -> np.ndarray:
    """Decode *path* into an HxWx4 RGBA array, the pixels as the viewer shows them.

    Handles camera RAW (developed through libraw), SVG, a video's poster frame,
    HEIC / JPEG XL and every Pillow format. Rasters are converted to sRGB from
    an embedded colour profile and, with *orient*, turned upright by their EXIF
    orientation. No recipe and no view-time simulation: this is the base an
    editor (Modify, Paint) works on. *thumbnail* favours a fast, downscaled
    decode (RAW embedded preview, 1600 px rasters).
    """
    ext = Path(path).suffix.lower()
    if ext in RAW_EXTENSIONS:
        img_data = _load_raw(path, thumbnail)
    elif ext == ".svg":
        img_data = _load_svg(path, thumbnail=thumbnail)
    elif ext in VIDEO_EXTENSIONS:
        img_data = poster_frame(path)
    else:
        ensure_pillow_opener(ext)
        img_data = (_load_raster_thumbnail(path, orient=orient) if thumbnail
                    else _load_raster(path, orient=orient))
    return _ensure_rgba(img_data)


def decode_image(path, *, max_edge: int | None = None) -> Image.Image:
    """:func:`decode_image_file` as a Pillow image: RGB when every pixel is opaque, else RGBA.

    What a file written from the viewer's pixels starts from (a thumbnail, a
    PDF page, a converted copy): camera RAW developed, sRGB, upright. With
    *max_edge* the long side is scaled down to it, through the fast thumbnail
    decode (a RAW's embedded preview, a 1600 px raster) when that is big enough.
    """
    fast = max_edge is not None and max_edge <= _THUMBNAIL_EDGE
    img = Image.fromarray(decode_image_file(path, thumbnail=fast), "RGBA")
    if max_edge is not None:
        img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    if img.getextrema()[3] == (255, 255):
        img = img.convert("RGB")
    return img


def load_image_file(path, thumbnail=False, recipe=None):
    """
    支援一般圖片 + RAW 檔案
    thumbnail=True 時會優先使用 RAW embedded preview 或 half_size
    回傳 numpy RGBA

    ``recipe`` 是可選的 :class:`Imervue.image.recipe.Recipe`: 若提供, 非 identity
    的部分會在回傳前套到 RGBA 陣列上. 呼叫端也可以先自行查 recipe_store 再決定
    要不要傳進來, 這個函式不強制依賴 store.

    點陣圖依 EXIF Orientation 轉正; 例外是 recipe 的幾何是在轉正之前設定的
    (``Recipe.base_is_oriented``), 那種 recipe 仍套在原始方向上.
    """
    img_data = decode_image_file(
        path, thumbnail=thumbnail, orient=recipe is None or recipe.base_is_oriented(),
    )

    if recipe is not None and not recipe.is_identity():
        try:
            img_data = recipe.apply(img_data)
        except Exception as exc:  # noqa: BLE001
            # 一張圖片的 recipe 壞掉不該害整個載入流程炸掉; log 一下繼續用
            # 原始像素. 使用者下一次打開 Develop panel 會看到 reset 過的值.
            logger.warning(f"Recipe apply failed for {path}: {exc}")

    # View-time CVD simulation — applied AFTER the recipe so the
    # user sees how their *edited* image looks under the simulation.
    # No-op when the mode is off (the common case); the helper short-
    # circuits cheaply via ``is_active``.
    from Imervue.gpu_image_view.cvd_view_mode import apply_if_active
    img_data = apply_if_active(img_data)

    return img_data


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


# ================================================================
# 開啟路徑（資料夾或檔案）
# ================================================================


def open_path(main_gui: GPUImageView, path: str):
    path_obj = Path(path)
    # *path* is the user's own local selection in this desktop viewer, not
    # untrusted remote input; the taint warnings on these probes are false
    # positives for that threat model.
    if path_obj.is_dir():  # NOSONAR
        _open_folder(main_gui, path_obj)
    elif path_obj.is_file() and path_obj.suffix.lower() in VIEWER_EXTENSIONS:  # NOSONAR
        _open_file(main_gui, path_obj)
