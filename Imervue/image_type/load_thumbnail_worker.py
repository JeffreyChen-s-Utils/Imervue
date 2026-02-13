from PySide6.QtCore import QRunnable, Signal, QObject
import numpy as np
import os
import rawpy
import imageio
from PIL import Image

# ===== 如果沒有 load_image_file 就複製同樣邏輯 =====

class WorkerSignals(QObject):
    finished = Signal(object, str)


class LoadThumbnailWorker(QRunnable):

    def __init__(self, path, size):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = WorkerSignals()
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        if self._abort:
            return

        try:
            ext = os.path.splitext(self.path)[1].lower()
            raw_exts = [".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"]

            # ===== RAW =====
            if ext in raw_exts:
                with rawpy.imread(self.path) as raw:
                    try:
                        thumb = raw.extract_thumb()
                        if thumb.format == rawpy.ThumbFormat.JPEG:
                            img = imageio.imread(thumb.data)
                        elif thumb.format == rawpy.ThumbFormat.BITMAP:
                            img = thumb.data
                        else:
                            raise Exception
                    except Exception:
                        img = raw.postprocess(
                            half_size=True,
                            use_camera_wb=True,
                            output_bps=8
                        )

                img_data = img

            # ===== 一般圖片 =====
            else:
                img = Image.open(self.path).convert("RGBA")
                img = img.resize(
                    (self.size, self.size),
                    Image.Resampling.LANCZOS
                )

                img_data = np.array(img)

            # 補 alpha
            if img_data.shape[2] == 3:
                alpha = np.ones((*img_data.shape[:2], 1), dtype=np.uint8) * 255
                img_data = np.concatenate([img_data, alpha], axis=2)

            if not self._abort:
                self.signals.finished.emit(img_data, self.path)

        except Exception as e:
            print(f"Thumbnail load failed: {self.path} - {e}")
