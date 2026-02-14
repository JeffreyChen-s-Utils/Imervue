from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.image_type.pyramid import DeepZoomImage
from Imervue.image_type.tile_manager import TileManager

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

import os

import imageio
import numpy as np
import rawpy
from PIL import Image


def load_image_file(path, thumbnail=False):
    """
    支援一般圖片 + RAW 檔案
    thumbnail=True 時會優先使用 RAW embedded preview 或 half_size
    回傳 numpy RGBA
    """
    ext = os.path.splitext(path)[1].lower()

    raw_exts = [".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"]

    # ===== RAW 檔案 =====
    if ext in raw_exts:
        with rawpy.imread(path) as raw:

            # ---- Thumbnail 模式 ----
            if thumbnail:
                # 優先讀 embedded preview
                try:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        img = imageio.v3.imread(thumb.data)
                    elif thumb.format == rawpy.ThumbFormat.BITMAP:
                        img = thumb.data
                    else:
                        raise Exception("No valid embedded preview")
                except Exception:
                    # fallback 用 half_size
                    img = raw.postprocess(
                        half_size=True,
                        use_camera_wb=True,
                        output_bps=8
                    )
            else:
                # ---- 全解析 ----
                img = raw.postprocess(
                    use_camera_wb=True,
                    no_auto_bright=False,
                    output_bps=8
                )

        img_data = img

    # ===== 一般圖片 =====
    else:
        img = Image.open(path).convert("RGBA")
        img_data = np.array(img)

    # ===== 補 alpha =====
    if img_data.shape[2] == 3:
        alpha = np.ones((*img_data.shape[:2], 1), dtype=np.uint8) * 255
        img_data = np.concatenate([img_data, alpha], axis=2)

    return img_data

def load_image(path: str, main_gui: GPUImageView):
    img = Image.open(path).convert("RGBA")
    img_data = np.array(img)
    main_gui.deep_zoom = DeepZoomImage(img_data)
    main_gui.tile_manager = TileManager(main_gui.deep_zoom)
    main_gui.zoom = 1.0
    # 居中
    main_gui.offset_x = (main_gui.width() - img_data.shape[1]) / 2
    main_gui.offset_y = (main_gui.height() - img_data.shape[0]) / 2
    main_gui.update()

def switch_back_to_grid(main_gui: GPUImageView):

    # 1️⃣ 停止 DeepZoom tile manager
    if main_gui.tile_manager:
        main_gui.clear_tile_grid()
        main_gui.tile_manager = None
        main_gui.deep_zoom_mode = False

    main_gui.deep_zoom = None

    main_gui.tile_grid_mode = True

    main_gui.zoom = 1.0
    main_gui.dz_offset_x = 0
    main_gui.dz_offset_y = 0

    main_gui.update()

