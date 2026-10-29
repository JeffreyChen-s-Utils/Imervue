"""
AI 圖片放大的背景工作
Background worker of the AI upscale dialog.

``_UpscaleWorker`` runs a traditional resample or the ONNX model over every
path, records each result on its ``JobState`` and always emits ``result_ready``,
even when the model download or session build fails.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from Imervue.gui.ai_upscale_engine import (
    UPSCALE_MODELS, _TRAD_PREFIX, _TRAD_RESAMPLING, _ai_upscale, _download_model,
    _preferred_providers,
)
from Imervue.gui.export_source import upright_image
from Imervue.image.in_place_save import (
    can_rewrite_in_place, in_place_format, save_edited_copy, save_over_source,
)
from Imervue.system.job_state import JobState

logger = logging.getLogger("Imervue.ai_upscale")


class _UpscaleWorker(QThread):
    progress = Signal(int, int, str)  # current_image, total_images, status
    tile_progress = Signal(int, int)  # tile_done, tile_total
    result_ready = Signal(int, int)   # success, failed

    def __init__(self, paths: list[str], output_dir: str,
                 model_key: str, overwrite: bool,
                 scale_override: int = 0):
        super().__init__()
        self._paths = list(dict.fromkeys(paths))
        self._output_dir = output_dir
        self._model_key = model_key
        self._overwrite = overwrite
        # For traditional methods the caller supplies the scale explicitly.
        self._scale_override = scale_override
        self.job_state = JobState(self._paths)

    # -- helpers -------------------------------------------------------------

    def _skip_unwritable(self, src: str) -> bool:
        """In overwrite mode, whether *src* must be left alone: a save over it
        would drop an animation's or a multi-page file's other frames."""
        if self._overwrite and not can_rewrite_in_place(src):
            logger.warning("Not overwriting %s: it can't be saved back whole", src)
            return True
        return False

    @staticmethod
    def _output_path(src: str, output_dir: str, scale: int,
                     overwrite: bool) -> str:
        if overwrite:
            return src
        stem = Path(src).stem
        # A RAW / HEIC / SVG source can't be written back in its own format.
        suffix = Path(src).suffix if in_place_format(src) else ".png"
        dst = str(Path(output_dir) / f"{stem}_x{scale}{suffix}")
        counter = 1
        while os.path.exists(dst):
            dst = str(Path(output_dir)
                      / f"{stem}_x{scale}_{counter}{suffix}")
            counter += 1
        return dst

    def _save(self, src: str, img, dst: str) -> None:
        """Write the upscaled *img* to *dst* in one step, keeping *src*'s EXIF."""
        if self._overwrite:
            save_over_source(src, img)
        else:
            save_edited_copy(src, img, dst)

    # -- run -----------------------------------------------------------------

    def run(self):
        try:
            if self._model_key.startswith(_TRAD_PREFIX):
                self._run_traditional()
            else:
                self._run_ai()
        except Exception as exc:  # worker must always report
            # The onnxruntime import, model download and session build run
            # outside the per-image loop. If they fail (offline, HF unreachable,
            # missing dep) the thread would die and result_ready never fire,
            # stranding the dialog on "Downloading…" with Apply disabled forever.
            # Report all-failed so _on_finished resets the UI and toasts.
            logger.exception("Upscale run failed: %s", exc)
            self.job_state.finish(error=str(exc) or type(exc).__name__)
            self.result_ready.emit(0, len(self._paths))
        finally:
            if self.isInterruptionRequested():
                self.job_state.request_cancel()
            self.job_state.finish()

    def _run_traditional(self):
        from PIL import Image
        resample = getattr(Image.Resampling, _TRAD_RESAMPLING[self._model_key])
        scale = self._scale_override or 2
        self._upscale_each(
            scale, lambda img: img.resize((img.width * scale, img.height * scale), resample))

    def _run_ai(self):
        import onnxruntime as ort

        scale = UPSCALE_MODELS[self._model_key]["scale"]
        total = len(self._paths)
        self.progress.emit(0, total, "Downloading model...")
        model_path = _download_model(self._model_key)
        self.progress.emit(0, total, "Loading model...")
        session = ort.InferenceSession(
            model_path, providers=_preferred_providers(ort.get_available_providers()))
        self._upscale_each(
            scale, lambda img: _ai_upscale(session, img, scale, self.tile_progress.emit))

    def _upscale_each(self, scale: int, upscale) -> None:
        """Run *upscale* (an upright picture in, the enlarged one out) over every path.

        Reports progress per picture, stops when interrupted, counts as failed a
        file an overwrite can't save back whole or whose upscale raises, saves
        each result and emits the success / failure counts.
        """
        total = len(self._paths)
        success = failed = 0
        for i, src in enumerate(self._paths):
            if self.isInterruptionRequested() or self.job_state.cancelled:
                self.job_state.request_cancel()
                break
            self.progress.emit(i, total, Path(src).name)
            if self._skip_unwritable(src):
                self.job_state.record(src, error="Source cannot be rewritten without losing frames")
                failed += 1
                continue
            try:
                out_img = upscale(upright_image(src))
                if self.isInterruptionRequested() or self.job_state.cancelled:
                    self.job_state.request_cancel()
                    break
                dst = self._output_path(
                    src, self._output_dir, scale, self._overwrite)
                self._save(src, out_img, dst)
                self.job_state.record(src, output=dst)
                success += 1
            except Exception as exc:
                logger.exception("Upscale failed for %s: %s", src, exc,
                                 exc_info=True)
                self.job_state.record(src, error=str(exc) or type(exc).__name__)
                failed += 1
        self.result_ready.emit(success, failed)
