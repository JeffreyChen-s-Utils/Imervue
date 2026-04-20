import logging
from pathlib import Path

from PySide6.QtCore import QRunnable, Signal, QObject
import numpy as np
import rawpy
import imageio
from PIL import Image

from Imervue.image.recipe_store import recipe_store
from Imervue.image.thumbnail_disk_cache import thumbnail_disk_cache

logger = logging.getLogger("Imervue.thumbnail_worker")


class WorkerSignals(QObject):
    finished = Signal(object, str, int)  # img_data, path, generation


class LoadThumbnailWorker(QRunnable):

    def __init__(self, path, size=None, generation=0):
        super().__init__()
        self.path = path
        self.size = size      # None means use the original image size
        self.generation = generation
        self.signals = WorkerSignals()
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        if self._abort:
            return
        try:
            recipe = recipe_store.get_for_path(self.path)
            r_hash = recipe.recipe_hash() if recipe is not None else ""
            img_data = self._try_cache_lookup(r_hash)
            if img_data is None:
                img_data = self._bake_fresh(recipe, r_hash)
                if img_data is None:
                    return
            if not self._abort:
                self.signals.finished.emit(img_data, self.path, self.generation)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Thumbnail load failed: {self.path} - {e}")

    def _try_cache_lookup(self, r_hash: str):
        if self.size is None:
            return None
        return thumbnail_disk_cache.get(self.path, self.size, r_hash)

    def _bake_fresh(self, recipe, r_hash: str):
        img_data = self._load_by_extension()
        if self._abort:
            return None
        img_data = self._ensure_rgba(img_data)
        img_data = self._apply_recipe(img_data, recipe)
        if self.size is not None:
            thumbnail_disk_cache.put(self.path, self.size, img_data, r_hash)
        return img_data

    def _load_by_extension(self):
        ext = Path(self.path).suffix.lower()
        raw_exts = {".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"}
        if ext in raw_exts:
            return self._load_raw()
        if ext == ".svg":
            return self._load_svg()
        return self._load_standard()

    @staticmethod
    def _ensure_rgba(img_data: np.ndarray) -> np.ndarray:
        if img_data.ndim == 2:
            img_data = np.stack([img_data, img_data, img_data], axis=2)
        if img_data.shape[2] == 3:
            alpha = np.full((*img_data.shape[:2], 1), 255, dtype=np.uint8)
            img_data = np.concatenate([img_data, alpha], axis=2)
        return img_data

    def _apply_recipe(self, img_data, recipe):
        if recipe is None or recipe.is_identity():
            return img_data
        try:
            return recipe.apply(img_data)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Recipe apply failed for thumbnail {self.path}: {e}")
            return img_data

    def _load_standard(self) -> np.ndarray:
        """載入一般圖片，使用 thumbnail() 減少記憶體峰值"""
        img = Image.open(self.path)

        if self.size is not None:
            # thumbnail() 會用 draft() 跳過不需要的解碼，大幅降低記憶體
            img.thumbnail((self.size, self.size), Image.Resampling.LANCZOS)

        img = img.convert("RGBA")
        return np.array(img)

    def _load_svg(self) -> np.ndarray:
        """載入 SVG 圖片"""
        from Imervue.gpu_image_view.images.image_loader import _load_svg
        return _load_svg(self.path, thumbnail=(self.size is not None))

    def _load_raw(self) -> np.ndarray:
        """載入 RAW 圖片"""
        with rawpy.imread(self.path) as raw:
            try:
                thumb = raw.extract_thumb()

                if thumb.format == rawpy.ThumbFormat.JPEG:
                    img_data = imageio.v3.imread(thumb.data)
                elif thumb.format == rawpy.ThumbFormat.BITMAP:
                    img_data = thumb.data
                else:
                    raise ValueError("No valid embedded preview")

            except Exception:
                # fallback: 用 half_size 降低記憶體
                img_data = raw.postprocess(
                    half_size=(self.size is not None),
                    use_camera_wb=True,
                    output_bps=8
                )

        # 自動限制最大尺寸（避免爆 VRAM）
        if self.size is None:
            MAX_DIM = 2048
            h, w = img_data.shape[:2]
            if max(w, h) > MAX_DIM:
                scale = MAX_DIM / max(w, h)
                img_pil = Image.fromarray(img_data)
                img_pil.thumbnail((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
                img_data = np.array(img_pil)
        else:
            # 使用 thumbnail 保持比例並降低記憶體
            img_pil = Image.fromarray(img_data).convert("RGBA")
            img_pil.thumbnail((self.size, self.size), Image.Resampling.LANCZOS)
            img_data = np.array(img_pil)

        return img_data
