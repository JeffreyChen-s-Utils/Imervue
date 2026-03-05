from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from Imervue.image.pyramid import DeepZoomImage
from Imervue.image.tile_manager import TileManager

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

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
    ext = Path(path).suffix.lower()

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
    main_gui.tile_grid_mode = False
    img = Image.open(path).convert("RGBA")
    img_data = np.array(img)
    main_gui.deep_zoom = DeepZoomImage(img_data)
    main_gui.tile_manager = TileManager(main_gui.deep_zoom)
    main_gui.zoom = 1.0
    # 居中
    main_gui.offset_x = (main_gui.width() - img_data.shape[1]) / 2
    main_gui.offset_y = (main_gui.height() - img_data.shape[0]) / 2
    main_gui.update()

def open_path(main_gui: GPUImageView, path: str):

    path_obj = Path(path)

    supported_exts = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")

    if path_obj.is_dir():

        images = [
            str(p)
            for p in sorted(path_obj.iterdir())
            if p.suffix.lower() in supported_exts
        ]

        if not images:
            return

        main_gui.current_index = 0
        main_gui.load_tile_grid_async(images)

    elif path_obj.is_file() and path_obj.suffix.lower() in supported_exts:

        dir_path = path_obj.parent

        images = [
            str(p)
            for p in sorted(dir_path.iterdir())
            if p.suffix.lower() in supported_exts
        ]

        if not images:
            return

        main_gui.model.set_images(images)
        main_gui.current_index = images.index(str(path_obj))

        main_gui.tile_grid_mode = False
        main_gui.load_deep_zoom_image(str(path_obj))


