"""
圖片淨化背景工作
Image Sanitizer worker — a QThread that prepares the optional upscaler
(traditional resampling or an ONNX Real-ESRGAN session) once, then sanitizes
every path, mirroring the source subfolders under the output folder.
"""
from __future__ import annotations

import logging
import os

from PIL import Image
from PySide6.QtCore import QThread, Signal

from Imervue.gui.image_sanitize_core import SanitizeSettings, UpscaleSpec, sanitize_image

logger = logging.getLogger("Imervue.image_sanitize")


class _SanitizeWorker(QThread):
    progress = Signal(int, int, str)     # current, total, filename
    tile_progress = Signal(int, int)     # tile_done, tile_total
    result_ready = Signal(int, int)      # success, failed

    def __init__(self, paths: list[str], output_dir: str, settings: SanitizeSettings, *,
                 src_root: str | None = None, parent=None):
        super().__init__(parent)
        self._paths = paths
        self._output_dir = output_dir
        self._settings = settings
        self._src_root = src_root
        self._abort = False

    def _target_dir_for(self, path: str) -> str:
        """Mirror the source's subfolder structure under *output_dir*.

        If *src_root* is set, compute the file's directory relative to the
        source root and append it to *output_dir*. Paths that escape the
        source root (``..`` segments) fall back to the flat output dir so
        a crafted path can never write outside it.
        """
        if not self._src_root:
            return self._output_dir
        try:
            rel = os.path.relpath(os.path.dirname(path), self._src_root)
        except ValueError:
            return self._output_dir
        if rel in ("", ".") or rel.startswith(".."):
            return self._output_dir
        target = os.path.join(self._output_dir, rel)
        os.makedirs(target, exist_ok=True)
        return target

    def abort(self):
        self._abort = True

    def run(self):
        total = len(self._paths)
        trad_resampling, session, scale = self._prepare_upscale(total)
        success, failed = self._sanitize_all(total, trad_resampling, session, scale)
        self.result_ready.emit(success, failed)

    def _prepare_upscale(self, total: int):
        if self._settings.target_long_edge <= 0 or not self._settings.model_key:
            return None, None, 0
        if self._settings.model_key.startswith("trad:"):
            return self._resolve_trad_resampling(), None, 0
        return None, *self._load_ai_session(total)

    def _resolve_trad_resampling(self):
        from Imervue.gui.ai_upscale_dialog import _TRAD_RESAMPLING
        resampling_name = _TRAD_RESAMPLING.get(self._settings.model_key)
        if not resampling_name:
            return None
        return getattr(Image.Resampling, resampling_name)

    def _load_ai_session(self, total: int):
        try:
            from Imervue.gui.ai_upscale_dialog import (
                _download_model, UPSCALE_MODELS,
            )
            import onnxruntime as ort
            self.progress.emit(0, total, "Downloading AI model...")
            model_path = _download_model(self._settings.model_key)
            self.progress.emit(0, total, "Loading AI model...")
            providers = self._preferred_ort_providers(ort)
            session = ort.InferenceSession(model_path, providers=providers)
            scale = UPSCALE_MODELS[self._settings.model_key]["scale"]
            return session, scale
        except Exception:
            logger.exception("Failed to load AI upscale model")
            return None, 0

    @staticmethod
    def _preferred_ort_providers(ort) -> list[str]:
        available = ort.get_available_providers()
        preferred: list[str] = []
        if "CUDAExecutionProvider" in available:
            preferred.append("CUDAExecutionProvider")
        if "DmlExecutionProvider" in available:
            preferred.append("DmlExecutionProvider")
        preferred.append("CPUExecutionProvider")
        return preferred

    def _sanitize_all(self, total: int, trad_resampling, session, scale) -> tuple[int, int]:
        success = 0
        failed = 0
        for i, path in enumerate(self._paths):
            if self._abort:
                break
            self.progress.emit(i + 1, total, os.path.basename(path))
            try:
                sanitize_image(
                    path, self._target_dir_for(path), self._settings.output_ext,
                    rand_len=self._settings.rand_len,
                    jpeg_quality=self._settings.jpeg_quality,
                    png_compress=self._settings.png_compress,
                    upscale=UpscaleSpec(
                        target_long_edge=self._settings.target_long_edge,
                        trad_resampling=trad_resampling,
                        ort_session=session,
                        ort_scale=scale,
                        tile_progress_cb=self.tile_progress.emit if session else None,
                    ),
                )
                success += 1
            except Exception:
                logger.exception("Failed to sanitize %s", path)
                failed += 1
        return success, failed
