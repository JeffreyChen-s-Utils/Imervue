"""
AI 圖片放大 (Super Resolution)
AI Image Upscale — Real-ESRGAN via ONNX Runtime.

Models are automatically downloaded from HuggingFace on first use.
Dependencies: onnxruntime, huggingface_hub, numpy (all lightweight).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.pip_installer import ensure_dependencies

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.ai_upscale")

# ---------------------------------------------------------------------------
# Model registry — HuggingFace repo + filename for each variant
# ---------------------------------------------------------------------------
_HF_REPO = "facefool/Real-ESRGAN-ONNX"

UPSCALE_MODELS = {
    "realesrgan-x4plus": {
        "file": "RealESRGAN_x4plus.onnx",
        "scale": 4,
        "desc_key": "upscale_model_x4",
        "desc_default": "Real-ESRGAN x4 (general, best quality)",
    },
    "realesrgan-x4plus-anime": {
        "file": "RealESRGAN_x4plus_anime_6B.onnx",
        "scale": 4,
        "desc_key": "upscale_model_x4_anime",
        "desc_default": "Real-ESRGAN x4 Anime (optimized for illustrations)",
    },
    "realesrgan-x2plus": {
        "file": "RealESRGAN_x2plus.onnx",
        "scale": 2,
        "desc_key": "upscale_model_x2",
        "desc_default": "Real-ESRGAN x2 (general, 2x upscale)",
    },
}

REQUIRED_PACKAGES = [
    ("onnxruntime", "onnxruntime"),
    ("huggingface_hub", "huggingface_hub"),
]

_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
})

# Tile size for tiled inference (prevents OOM on large images)
_TILE_SIZE = 512
_TILE_PAD = 10


# ---------------------------------------------------------------------------
# ONNX inference helpers
# ---------------------------------------------------------------------------

def _download_model(model_key: str) -> str:
    """Download model from HF and return local path."""
    from huggingface_hub import hf_hub_download
    info = UPSCALE_MODELS[model_key]
    return hf_hub_download(repo_id=_HF_REPO, filename=info["file"])


def _upscale_tile(session, tile_arr):
    """Run ONNX inference on a single tile (HWC uint8 → HWC uint8)."""
    import numpy as np
    # Normalize to float32 [0, 1] and transpose to NCHW
    inp = tile_arr.astype(np.float32) / 255.0
    inp = np.transpose(inp, (2, 0, 1))[np.newaxis, ...]
    result = session.run(None, {session.get_inputs()[0].name: inp})[0]
    # Back to HWC uint8
    out = np.clip(result[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8)
    return out


def _upscale_image(session, img_arr, scale: int, progress_cb=None):
    """Tiled upscale for an entire image (HWC uint8 → HWC uint8).
    Tiles prevent GPU/CPU OOM on large images.
    """
    import numpy as np
    h, w, c = img_arr.shape
    tile = _TILE_SIZE
    pad = _TILE_PAD

    out_h, out_w = h * scale, w * scale
    output = np.zeros((out_h, out_w, c), dtype=np.uint8)

    tiles_y = (h + tile - 1) // tile
    tiles_x = (w + tile - 1) // tile
    total_tiles = tiles_y * tiles_x
    done = 0

    for yi in range(tiles_y):
        for xi in range(tiles_x):
            # Input tile with padding
            y0 = yi * tile
            x0 = xi * tile
            y1 = min(y0 + tile, h)
            x1 = min(x0 + tile, w)

            # Padded coords (clamped)
            py0 = max(0, y0 - pad)
            px0 = max(0, x0 - pad)
            py1 = min(h, y1 + pad)
            px1 = min(w, x1 + pad)

            tile_in = img_arr[py0:py1, px0:px1, :]
            tile_out = _upscale_tile(session, tile_in)

            # Compute where the non-padded region is in the output tile
            oy0 = (y0 - py0) * scale
            ox0 = (x0 - px0) * scale
            oh = (y1 - y0) * scale
            ow = (x1 - x0) * scale
            oy1 = oy0 + oh
            ox1 = ox0 + ow

            # Place in output
            out_y0 = y0 * scale
            out_x0 = x0 * scale
            output[out_y0:out_y0 + oh, out_x0:out_x0 + ow, :] = \
                tile_out[oy0:oy1, ox0:ox1, :]

            done += 1
            if progress_cb:
                progress_cb(done, total_tiles)

    return output


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class _UpscaleWorker(QThread):
    progress = Signal(int, int, str)  # current_image, total_images, status
    tile_progress = Signal(int, int)  # tile_done, tile_total
    result_ready = Signal(int, int)   # success, failed

    def __init__(self, paths: list[str], output_dir: str,
                 model_key: str, overwrite: bool):
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._model_key = model_key
        self._overwrite = overwrite

    def run(self):
        import numpy as np
        from PIL import Image
        import onnxruntime as ort

        info = UPSCALE_MODELS[self._model_key]
        scale = info["scale"]

        # Download + load model
        self.progress.emit(0, len(self._paths), "Downloading model...")
        model_path = _download_model(self._model_key)
        self.progress.emit(0, len(self._paths), "Loading model...")

        providers = ort.get_available_providers()
        # Prefer GPU if available
        preferred = []
        if "CUDAExecutionProvider" in providers:
            preferred.append("CUDAExecutionProvider")
        if "DmlExecutionProvider" in providers:
            preferred.append("DmlExecutionProvider")
        preferred.append("CPUExecutionProvider")
        session = ort.InferenceSession(model_path, providers=preferred)

        success = 0
        failed = 0
        total = len(self._paths)

        for i, src in enumerate(self._paths):
            name = Path(src).name
            self.progress.emit(i, total, name)
            try:
                img = Image.open(src)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")

                has_alpha = img.mode == "RGBA"
                if has_alpha:
                    alpha = img.split()[-1]
                    rgb = img.convert("RGB")
                else:
                    rgb = img
                    alpha = None

                arr = np.array(rgb)
                out_arr = _upscale_image(
                    session, arr, scale,
                    progress_cb=lambda d, t: self.tile_progress.emit(d, t),
                )
                out_img = Image.fromarray(out_arr)

                # Upscale alpha if present
                if alpha is not None:
                    alpha_up = alpha.resize(out_img.size, Image.Resampling.LANCZOS)
                    out_img.putalpha(alpha_up)

                # Output path
                if self._overwrite:
                    dst = src
                else:
                    stem = Path(src).stem
                    suffix = Path(src).suffix or ".png"
                    dst = str(Path(self._output_dir) / f"{stem}_x{scale}{suffix}")
                    counter = 1
                    while os.path.exists(dst):
                        dst = str(Path(self._output_dir)
                                  / f"{stem}_x{scale}_{counter}{suffix}")
                        counter += 1

                # Save
                fmt_map = {
                    ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
                    ".webp": "WEBP", ".bmp": "BMP",
                    ".tif": "TIFF", ".tiff": "TIFF",
                }
                ext = Path(dst).suffix.lower()
                fmt = fmt_map.get(ext, "PNG")
                if fmt == "JPEG" and out_img.mode == "RGBA":
                    out_img = out_img.convert("RGB")
                out_img.save(dst, format=fmt)
                success += 1
            except Exception as exc:
                logger.error("Upscale failed for %s: %s", src, exc,
                             exc_info=True)
                failed += 1

        self.result_ready.emit(success, failed)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class AIUpscaleDialog(QDialog):
    def __init__(self, main_gui: GPUImageView,
                 paths: list[str] | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths: list[str] = paths or []
        self._lang = language_wrapper.language_word_dict
        self._worker = None

        self.setWindowTitle(
            self._lang.get("upscale_title", "AI Image Upscale"))
        self.setMinimumWidth(520)
        self._build_ui()

        if self._paths:
            self._update_count()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(self._lang.get(
            "upscale_info",
            "Upscale images using Real-ESRGAN AI model. "
            "Models are downloaded automatically on first use (~65 MB)."))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Image count
        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

        # Model selection
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel(
            self._lang.get("upscale_model", "Model:")))
        self._model_combo = QComboBox()
        for key, info_dict in UPSCALE_MODELS.items():
            label = self._lang.get(info_dict["desc_key"],
                                   info_dict["desc_default"])
            self._model_combo.addItem(label, key)
        model_row.addWidget(self._model_combo, 1)
        layout.addLayout(model_row)

        # Overwrite
        self._overwrite_check = QCheckBox(
            self._lang.get("upscale_overwrite",
                           "Overwrite original files"))
        self._overwrite_check.setChecked(False)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

        # Output directory
        self._out_label = QLabel(
            self._lang.get("upscale_output", "Output folder:"))
        layout.addWidget(self._out_label)
        out_row = QHBoxLayout()
        self._out_edit = QLineEdit()
        if self._paths:
            self._out_edit.setText(str(Path(self._paths[0]).parent))
        self._out_browse = QPushButton(
            self._lang.get("export_browse", "Browse..."))
        self._out_browse.clicked.connect(self._browse_out)
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(self._out_browse)
        layout.addLayout(out_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._tile_progress = QProgressBar()
        self._tile_progress.setFormat(
            self._lang.get("upscale_tile_progress",
                           "Tile: %v / %m") + "  (%p%)")
        self._tile_progress.setVisible(False)
        layout.addWidget(self._tile_progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton(
            self._lang.get("upscale_start", "Upscale"))
        self._start_btn.clicked.connect(self._do_start)
        self._start_btn.setEnabled(bool(self._paths))
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._start_btn)
        layout.addLayout(btn_row)

    def _update_count(self):
        count = len(self._paths)
        self._count_label.setText(
            self._lang.get("upscale_count",
                           "{count} image(s)").format(count=count))
        self._start_btn.setEnabled(count > 0)

    def _on_overwrite_toggled(self, checked):
        self._out_label.setVisible(not checked)
        self._out_edit.setVisible(not checked)
        self._out_browse.setVisible(not checked)

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("upscale_output", "Output folder"))
        if folder:
            self._out_edit.setText(folder)

    def _do_start(self):
        if not self._paths:
            return

        overwrite = self._overwrite_check.isChecked()
        output_dir = "" if overwrite else self._out_edit.text().strip()
        if not overwrite:
            if not output_dir:
                return
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        model_key = self._model_combo.currentData()
        self._start_btn.setEnabled(False)
        self._model_combo.setEnabled(False)
        self._overwrite_check.setEnabled(False)
        self._status_label.setText(
            self._lang.get("upscale_installing",
                           "Installing dependencies..."))

        def _on_deps_ready():
            self._progress.setMaximum(len(self._paths))
            self._progress.setValue(0)
            self._progress.setVisible(True)
            self._tile_progress.setVisible(True)
            self._status_label.setText("")

            self._worker = _UpscaleWorker(
                self._paths, output_dir, model_key, overwrite)
            self._worker.progress.connect(self._on_progress)
            self._worker.tile_progress.connect(self._on_tile_progress)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        try:
            ensure_dependencies(
                self._gui.main_window, REQUIRED_PACKAGES, _on_deps_ready)
        except Exception:
            logger.error("ensure_dependencies raised", exc_info=True)
            self._start_btn.setEnabled(True)

    def _on_progress(self, current, total, status):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {status}")

    def _on_tile_progress(self, done, total):
        self._tile_progress.setMaximum(total)
        self._tile_progress.setValue(done)

    def _cleanup(self):
        self._worker = None

    def _on_finished(self, success, failed):
        self._progress.setValue(len(self._paths))
        self._tile_progress.setVisible(False)
        self._start_btn.setEnabled(True)
        self._model_combo.setEnabled(True)
        self._overwrite_check.setEnabled(True)

        msg = self._lang.get(
            "upscale_done",
            "Done — {success} upscaled, {failed} failed."
        ).format(success=success, failed=failed)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)

        # Reload viewer if overwritten
        if self._overwrite_check.isChecked():
            try:
                if self._gui.tile_grid_mode:
                    self._gui.load_tile_grid_async(list(self._gui.model.images))
                elif self._gui.deep_zoom:
                    images = self._gui.model.images
                    if images and 0 <= self._gui.current_index < len(images):
                        self._gui._clear_deep_zoom()
                        self._gui.load_deep_zoom_image(
                            images[self._gui.current_index])
            except Exception:
                pass

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def open_ai_upscale(main_gui: GPUImageView):
    """Open upscale dialog with all images in current folder."""
    paths = list(main_gui.model.images) if main_gui.model.images else []
    dlg = AIUpscaleDialog(main_gui, paths=paths)
    dlg.exec()


def open_ai_upscale_single(main_gui: GPUImageView, path: str):
    """Open upscale dialog for a single image."""
    dlg = AIUpscaleDialog(main_gui, paths=[path])
    dlg.exec()


def open_ai_upscale_batch(main_gui: GPUImageView):
    """Open upscale dialog with selected tiles."""
    paths = list(main_gui.selected_tiles) if main_gui.selected_tiles else []
    if not paths:
        return
    dlg = AIUpscaleDialog(main_gui, paths=paths)
    dlg.exec()
