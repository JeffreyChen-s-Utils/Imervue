import math

import numpy as np
from PIL import Image


class DeepZoomImage:
    def __init__(self, image_array):
        self.levels = []
        self.build_pyramid(image_array)

    def build_pyramid(self, image):
        current = image
        self.levels.append(current)

        while min(current.shape[:2]) > 512:
            h, w = current.shape[:2]
            new_h, new_w = h // 2, w // 2
            # 使用 PIL LANCZOS 進行高品質降採樣，避免鋸齒
            channels = current.shape[2] if current.ndim == 3 else 1
            if channels == 4:
                pil_img = Image.fromarray(current, "RGBA")
            elif channels == 3:
                pil_img = Image.fromarray(current, "RGB")
            else:
                pil_img = Image.fromarray(current)
            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            current = np.array(pil_img)
            self.levels.append(current)

    def get_level(self, zoom):
        # zoom 1.0 = full res
        level = int(max(0, min(len(self.levels)-1, -math.log2(zoom))))
        return level, self.levels[level]
