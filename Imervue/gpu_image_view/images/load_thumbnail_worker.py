from PySide6.QtCore import QRunnable, Signal, QObject
import numpy as np
import os
import rawpy
import imageio
from PIL import Image


class WorkerSignals(QObject):
    finished = Signal(object, str)


class LoadThumbnailWorker(QRunnable):

    def __init__(self, path, size=None):
        super().__init__()
        self.path = path
        self.size = size      # None = 使用原圖尺寸
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

            # RAW 圖片
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
                        # fallback: 用 half_size 比較安全
                        img = raw.postprocess(
                            half_size=(self.size is not None),
                            use_camera_wb=True,
                            output_bps=8
                        )

                img_data = img

                # 自動限制最大尺寸（避免爆 VRAM）
                if self.size is None:  # 只有使用原圖模式才限制
                    MAX_DIM = 2048

                    h, w = img_data.shape[:2]
                    max_current = max(w, h)

                    if max_current > MAX_DIM:
                        scale = MAX_DIM / max_current
                        new_w = int(w * scale)
                        new_h = int(h * scale)

                        img_pil = Image.fromarray(img_data)
                        img_pil = img_pil.resize(
                            (new_w, new_h),
                            Image.Resampling.LANCZOS
                        )
                        img_data = np.array(img_pil)

                # 如果有指定 size，縮放
                if self.size is not None:
                    img_pil = Image.fromarray(img_data).convert("RGBA")
                    img_pil = img_pil.resize(
                        (self.size, self.size),
                        Image.Resampling.LANCZOS
                    )
                    img_data = np.array(img_pil)

            # 一般圖片
            else:
                img = Image.open(self.path).convert("RGBA")

                if self.size is not None:
                    img = img.resize(
                        (self.size, self.size),
                        Image.Resampling.LANCZOS
                    )

                img_data = np.array(img)

            # 保證有 Alpha
            if img_data.shape[2] == 3:
                alpha = np.ones((*img_data.shape[:2], 1), dtype=np.uint8) * 255
                img_data = np.concatenate([img_data, alpha], axis=2)

            if not self._abort:
                self.signals.finished.emit(img_data, self.path)

        except Exception as e:
            print(f"Thumbnail load failed: {self.path} - {e}")
