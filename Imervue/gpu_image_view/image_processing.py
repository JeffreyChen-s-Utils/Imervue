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