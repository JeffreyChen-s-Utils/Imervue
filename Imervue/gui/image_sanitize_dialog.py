"""
圖片淨化重繪工具
Image Sanitizer — losslessly re-render images from raw pixel data,
stripping ALL hidden data (metadata, EXIF, steganography, trailing
bytes, alternate streams) and renaming with date + random string.

Optionally upscale to a common target resolution using AI (Real-ESRGAN)
or traditional resampling methods (Lanczos, Bicubic, Nearest) while
keeping aspect ratio.
"""
from __future__ import annotations

import logging
import os
import secrets
import string
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.image_sanitize")

# ---------------------------------------------------------------------------
# Common target resolutions (label, long_edge_px)
# "long_edge" means the longer side of the output; the shorter side is
# computed to maintain the original aspect ratio.
# ---------------------------------------------------------------------------
TARGET_RESOLUTIONS = [
    ("sanitize_res_none",   "No upscale",          0),
    ("sanitize_res_1080p",  "Full HD  (1920 px)",   1920),
    ("sanitize_res_2k",     "2K       (2560 px)",   2560),
    ("sanitize_res_4k",     "4K UHD   (3840 px)",   3840),
    ("sanitize_res_5k",     "5K       (5120 px)",   5120),
    ("sanitize_res_8k",     "8K UHD   (7680 px)",   7680),
]

_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".bmp",
})

_PIL_FORMAT_MAP = {
    ".jpg": "JPEG", ".jpeg": "JPEG",
    ".png": "PNG", ".tiff": "TIFF", ".tif": "TIFF",
    ".webp": "WebP", ".bmp": "BMP",
}

_RANDOM_CHARS = string.ascii_lowercase + string.digits


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _scan_folder(folder: str, recursive: bool = False) -> list[str]:
    """Return image paths sorted by name."""
    result: list[str] = []
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in _IMAGE_EXTS:
                    result.append(os.path.join(root, f))
    else:
        try:
            for entry in os.scandir(folder):
                if entry.is_file() and Path(entry.name).suffix.lower() in _IMAGE_EXTS:
                    result.append(entry.path)
        except OSError:
            pass
    result.sort(key=lambda p: os.path.basename(p).lower())
    return result


# ---------------------------------------------------------------------------
# Core sanitize logic (pure, testable)
# ---------------------------------------------------------------------------

def _get_image_date(path: str) -> datetime:
    """Extract the best date for an image: EXIF DateTimeOriginal > file mtime."""
    with contextlib.suppress(Exception):
        img = Image.open(path)
        exif = img.getexif()
        # 36867 = DateTimeOriginal, 306 = DateTime
        for tag in (36867, 306):
            val = exif.get(tag)
            if val:
                for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(val, fmt)
                    except (ValueError, TypeError):
                        continue
    # Fallback to file modification time
    try:
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime)
    except OSError:
        return datetime.now()


def _generate_name(dt: datetime, rand_len: int, ext: str) -> str:
    """Generate filename like 20260414_a3f8k2x1.png"""
    date_str = dt.strftime("%Y%m%d")
    rand_str = "".join(secrets.choice(_RANDOM_CHARS) for _ in range(rand_len))
    return f"{date_str}_{rand_str}{ext}"


def _compute_upscale_params(width: int, height: int,
                            target_long_edge: int) -> tuple[str, int, int]:
    """Decide which AI model to use and the final resize dimensions.

    Returns (model_key, final_w, final_h).
    If no upscale is needed returns ("", width, height).
    """
    long = max(width, height)
    if target_long_edge <= 0 or long >= target_long_edge:
        return ("", width, height)

    ratio = target_long_edge / long
    # Pick the smallest model that gets us past the target so we only
    # need to downscale afterward (higher quality than up-then-up).
    model_key = "realesrgan-x2plus" if ratio <= 2.0 else "realesrgan-x4plus"

    # Final size preserving aspect ratio
    if width >= height:
        final_w = target_long_edge
        final_h = max(1, round(height * target_long_edge / width))
    else:
        final_h = target_long_edge
        final_w = max(1, round(width * target_long_edge / height))
    return (model_key, final_w, final_h)


def sanitize_image(path: str, output_dir: str, output_ext: str,
                   rand_len: int = 8, jpeg_quality: int = 95,
                   png_compress: int = 6,
                   target_long_edge: int = 0,
                   ort_session=None,
                   ort_scale: int = 0,
                   tile_progress_cb=None,
                   trad_resampling=None) -> str:
    """Re-render an image from raw pixels, removing ALL hidden data.

    If *target_long_edge* > 0 and the image is smaller, it is upscaled
    using either *trad_resampling* (a PIL Resampling enum) or the
    provided *ort_session* (ONNX Real-ESRGAN), then resized to exactly
    fit the target while keeping aspect ratio.

    Returns the output path on success.  Raises on failure.
    """
    img = Image.open(path)

    # Determine output format
    if output_ext == "same":
        ext = Path(path).suffix.lower()
        if ext not in _PIL_FORMAT_MAP:
            ext = ".png"
    else:
        ext = output_ext
    fmt = _PIL_FORMAT_MAP.get(ext, "PNG")

    # Re-create image from raw bytes — no metadata survives, no list copy
    clean = Image.frombytes(img.mode, img.size, img.tobytes())

    # JPEG does not support alpha
    if fmt == "JPEG" and clean.mode != "RGB":
        clean = clean.convert("RGB")

    # --- Optional upscale ---
    if target_long_edge > 0:
        w, h = clean.size
        long = max(w, h)
        if long < target_long_edge:
            # Compute final dimensions preserving aspect ratio
            if w >= h:
                final_w = target_long_edge
                final_h = max(1, round(h * target_long_edge / w))
            else:
                final_h = target_long_edge
                final_w = max(1, round(w * target_long_edge / h))

            if trad_resampling is not None:
                # Traditional resize — single step, no ONNX needed
                clean = clean.resize((final_w, final_h), trad_resampling)
            elif ort_session is not None and ort_scale > 0:
                # AI upscale via ONNX
                import numpy as np
                from Imervue.gui.ai_upscale_dialog import _upscale_image

                if clean.mode == "RGBA":
                    alpha = clean.split()[-1]
                    rgb = clean.convert("RGB")
                else:
                    alpha = None
                    rgb = clean

                arr = np.array(rgb)
                upscaled_arr = _upscale_image(
                    ort_session, arr, ort_scale,
                    progress_cb=tile_progress_cb)
                upscaled = Image.fromarray(upscaled_arr)

                if alpha is not None:
                    alpha_up = alpha.resize(upscaled.size,
                                            Image.Resampling.LANCZOS)
                    upscaled.putalpha(alpha_up)

                clean = upscaled.resize((final_w, final_h),
                                        Image.Resampling.LANCZOS)

    # Disrupt LSB steganography (e.g. NovelAI stealth pnginfo embeds
    # prompt/seed/parameters in the least-significant bit of RGB/alpha
    # channels — tEXt-chunk stripping alone leaves that payload intact
    # because the bits live in the pixel data). Randomising each 8-bit
    # channel's LSB destroys the payload; the visual impact is ±1/255
    # per channel (well below the JND for any display).
    clean = _scramble_lsb(clean)

    # Generate new filename
    dt = _get_image_date(path)
    name = _generate_name(dt, rand_len, ext)
    out_path = os.path.join(output_dir, name)

    # Avoid collision
    while os.path.exists(out_path):
        name = _generate_name(dt, rand_len, ext)
        out_path = os.path.join(output_dir, name)

    # Save with minimal kwargs — no metadata passed
    save_kwargs: dict = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs["quality"] = jpeg_quality
        save_kwargs["subsampling"] = 0  # 4:4:4 best quality
    elif fmt == "PNG":
        save_kwargs["compress_level"] = png_compress

    clean.save(out_path, **save_kwargs)
    return out_path


# Fraction of channel-elements whose LSB is randomised. At 0.5 the net
# per-pixel change rate is 12.5% (halved from dense scrambling) while the
# probability any 120-bit magic header survives intact drops to 0.75^120
# ≈ 1.2e-15 — still comprehensive destruction, with half the visual
# perturbation in flat regions that synthetic AI art tends to produce.
_LSB_SCRAMBLE_RATE = 0.5


def _scramble_lsb(img: Image.Image) -> Image.Image:
    """Sparsely randomise the LSB of every 8-bit channel.

    Breaks LSB-steganography schemes such as NovelAI's stealth pnginfo.
    Only a fraction of LSBs (``_LSB_SCRAMBLE_RATE``) are touched — enough
    to obliterate any bit-sequential payload statistically, while keeping
    perceptual impact minimal in the flat regions common to synthetic
    imagery. Non 8-bit modes are converted first so palette/1-bit images
    are also covered.
    """
    import numpy as np
    # Convert exotic modes to a form with 8-bit channels so the LSB
    # operation is well-defined (palette indices, for example, would be
    # corrupted by masking).
    if img.mode not in ("L", "LA", "RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")
    arr = np.array(img, copy=True)
    rng = np.random.default_rng()
    scramble_mask = rng.random(size=arr.shape, dtype=np.float32) < _LSB_SCRAMBLE_RATE
    noise = rng.integers(0, 2, size=arr.shape, dtype=arr.dtype)
    # Where mask is True use random LSB, otherwise keep the original LSB.
    new_lsb = np.where(scramble_mask, noise, arr & np.uint8(0x01))
    arr = (arr & np.uint8(0xFE)) | new_lsb.astype(arr.dtype)
    return Image.fromarray(arr, mode=img.mode)


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class _SanitizeWorker(QThread):
    progress = Signal(int, int, str)     # current, total, filename
    tile_progress = Signal(int, int)     # tile_done, tile_total
    result_ready = Signal(int, int)      # success, failed

    def __init__(self, paths: list[str], output_dir: str, output_ext: str,
                 rand_len: int, jpeg_quality: int, png_compress: int,
                 target_long_edge: int = 0, model_key: str = "",
                 src_root: str | None = None,
                 parent=None):
        super().__init__(parent)
        self._paths = paths
        self._output_dir = output_dir
        self._output_ext = output_ext
        self._rand_len = rand_len
        self._jpeg_quality = jpeg_quality
        self._png_compress = png_compress
        self._target_long_edge = target_long_edge
        self._model_key = model_key
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
        success = 0
        failed = 0

        # Determine upscale mode
        is_traditional = self._model_key.startswith("trad:")
        trad_resampling = None
        session = None
        scale = 0

        if self._target_long_edge > 0 and self._model_key:
            if is_traditional:
                from Imervue.gui.ai_upscale_dialog import _TRAD_RESAMPLING
                resampling_name = _TRAD_RESAMPLING.get(self._model_key)
                if resampling_name:
                    trad_resampling = getattr(Image.Resampling,
                                              resampling_name)
            else:
                # AI model — prepare ONNX session
                try:
                    from Imervue.gui.ai_upscale_dialog import (
                        _download_model, UPSCALE_MODELS,
                    )
                    import onnxruntime as ort

                    self.progress.emit(0, total, "Downloading AI model...")
                    model_path = _download_model(self._model_key)
                    self.progress.emit(0, total, "Loading AI model...")

                    providers = ort.get_available_providers()
                    preferred = []
                    if "CUDAExecutionProvider" in providers:
                        preferred.append("CUDAExecutionProvider")
                    if "DmlExecutionProvider" in providers:
                        preferred.append("DmlExecutionProvider")
                    preferred.append("CPUExecutionProvider")
                    session = ort.InferenceSession(model_path,
                                                   providers=preferred)
                    scale = UPSCALE_MODELS[self._model_key]["scale"]
                except Exception:
                    logger.exception("Failed to load AI upscale model")
                    # Continue without upscale

        for i, path in enumerate(self._paths):
            if self._abort:
                break
            name = os.path.basename(path)
            self.progress.emit(i + 1, total, name)
            try:
                target_dir = self._target_dir_for(path)
                sanitize_image(
                    path, target_dir, self._output_ext,
                    self._rand_len, self._jpeg_quality, self._png_compress,
                    target_long_edge=self._target_long_edge,
                    ort_session=session,
                    ort_scale=scale,
                    tile_progress_cb=self.tile_progress.emit if session else None,
                    trad_resampling=trad_resampling,
                )
                success += 1
            except Exception:
                logger.exception("Failed to sanitize %s", path)
                failed += 1
        self.result_ready.emit(success, failed)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class ImageSanitizeDialog(QDialog):
    def __init__(self, main_gui: GPUImageView, folder: str | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._lang = language_wrapper.language_word_dict
        self._worker: _SanitizeWorker | None = None

        self.setWindowTitle(
            self._lang.get("sanitize_title", "Image Sanitizer"))
        self.setMinimumSize(620, 480)
        self._build_ui()

        if folder and os.path.isdir(folder):
            self._src_edit.setText(folder)

    def _build_ui(self):
        lang = self._lang
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(lang.get(
            "sanitize_info",
            "Re-render images from raw pixels, removing ALL hidden data "
            "(EXIF, metadata, steganographic content, trailing bytes). "
            "Files are renamed with date + random string."))
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(4)

        # Source folder
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel(lang.get("sanitize_source", "Source folder:")))
        self._src_edit = QLineEdit()
        src_row.addWidget(self._src_edit, 1)
        browse_src = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        browse_src.clicked.connect(self._browse_src)
        src_row.addWidget(browse_src)
        layout.addLayout(src_row)

        # Recursive
        self._recursive_check = QCheckBox(
            lang.get("duplicate_recursive", "Include subfolders"))
        layout.addWidget(self._recursive_check)

        # Output folder
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("organizer_output", "Output folder:")))
        self._out_edit = QLineEdit()
        out_row.addWidget(self._out_edit, 1)
        browse_out = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        browse_out.clicked.connect(self._browse_out)
        out_row.addWidget(browse_out)
        layout.addLayout(out_row)

        # Output format
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(
            lang.get("sanitize_output_format", "Output format:")))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItem(
            lang.get("sanitize_fmt_same", "Same as source"), "same")
        self._fmt_combo.addItem("PNG (.png)", ".png")
        self._fmt_combo.addItem("JPEG (.jpg)", ".jpg")
        self._fmt_combo.addItem("WebP (.webp)", ".webp")
        self._fmt_combo.addItem("BMP (.bmp)", ".bmp")
        self._fmt_combo.addItem("TIFF (.tiff)", ".tiff")
        fmt_row.addWidget(self._fmt_combo, 1)
        layout.addLayout(fmt_row)

        # Random string length
        rand_row = QHBoxLayout()
        rand_row.addWidget(QLabel(
            lang.get("sanitize_rand_len", "Random string length:")))
        self._rand_spin = QSpinBox()
        self._rand_spin.setRange(4, 32)
        self._rand_spin.setValue(8)
        rand_row.addWidget(self._rand_spin)
        rand_row.addStretch()
        layout.addLayout(rand_row)

        # JPEG quality
        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel(
            lang.get("sanitize_jpeg_quality", "JPEG quality:")))
        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(1, 100)
        self._quality_spin.setValue(95)
        quality_row.addWidget(self._quality_spin)
        quality_row.addStretch()
        layout.addLayout(quality_row)

        # --- AI Upscale group ---
        upscale_group = QGroupBox(
            lang.get("sanitize_upscale_group", "Upscale (optional)"))
        upscale_layout = QVBoxLayout(upscale_group)
        upscale_layout.setContentsMargins(6, 6, 6, 6)
        upscale_layout.setSpacing(4)

        upscale_info = QLabel(lang.get(
            "sanitize_upscale_info",
            "Upscale images smaller than the target to a common resolution. "
            "Traditional methods are lossless and fast; AI methods use "
            "Real-ESRGAN. Aspect ratio is preserved."))
        upscale_info.setWordWrap(True)
        upscale_layout.addWidget(upscale_info)

        res_row = QHBoxLayout()
        res_row.addWidget(QLabel(
            lang.get("sanitize_target_res", "Target resolution:")))
        self._res_combo = QComboBox()
        for key, fallback, px in TARGET_RESOLUTIONS:
            self._res_combo.addItem(lang.get(key, fallback), px)
        res_row.addWidget(self._res_combo, 1)
        upscale_layout.addLayout(res_row)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel(
            lang.get("upscale_model", "Model:")))
        self._model_combo = QComboBox()
        from Imervue.gui.ai_upscale_dialog import (
            UPSCALE_MODELS, TRADITIONAL_METHODS,
        )
        # Traditional methods first (no dependencies needed)
        for mkey, minfo in TRADITIONAL_METHODS.items():
            label = lang.get(minfo["desc_key"], minfo["desc_default"])
            self._model_combo.addItem(label, mkey)
        # AI models
        for mkey, minfo in UPSCALE_MODELS.items():
            label = lang.get(minfo["desc_key"], minfo["desc_default"])
            self._model_combo.addItem(label, mkey)
        model_row.addWidget(self._model_combo, 1)
        upscale_layout.addLayout(model_row)

        # Auto-select model hint
        self._model_hint = QLabel("")
        self._model_hint.setStyleSheet("color: gray; font-size: 11px;")
        upscale_layout.addWidget(self._model_hint)
        self._res_combo.currentIndexChanged.connect(self._on_res_changed)
        self._on_res_changed()

        layout.addWidget(upscale_group)

        # Progress
        self._progress = QProgressBar()
        self._progress.hide()
        layout.addWidget(self._progress)

        self._tile_progress = QProgressBar()
        self._tile_progress.setFormat("Tile: %v / %m  (%p%)")
        self._tile_progress.hide()
        layout.addWidget(self._tile_progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton(lang.get("organizer_start", "Start"))
        self._start_btn.clicked.connect(self._do_start)
        btn_row.addWidget(self._start_btn)
        btn_row.addStretch()
        close_btn = QPushButton(lang.get("export_cancel", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # --- Resolution hint ---

    def _on_res_changed(self):
        px = self._res_combo.currentData()
        if px and px > 0:
            self._model_combo.setEnabled(True)
            self._model_hint.setText(
                self._lang.get(
                    "sanitize_upscale_hint",
                    "Images with long edge < {px} px will be upscaled.")
                .replace("{px}", str(px)))
        else:
            self._model_combo.setEnabled(False)
            self._model_hint.setText("")

    # --- Browse ---

    def _browse_src(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("main_window_select_folder", "Select Folder"))
        if folder:
            self._src_edit.setText(folder)

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("main_window_select_folder", "Select Folder"))
        if folder:
            self._out_edit.setText(folder)

    # --- Run ---

    def _do_start(self):
        src = self._src_edit.text().strip()
        if not src or not os.path.isdir(src):
            return
        out = self._out_edit.text().strip()
        if not out:
            return

        recursive = self._recursive_check.isChecked()
        paths = _scan_folder(src, recursive)
        if not paths:
            self._status_label.setText(
                self._lang.get("sanitize_no_images",
                               "No supported images found."))
            return

        os.makedirs(out, exist_ok=True)

        output_ext = self._fmt_combo.currentData()
        rand_len = self._rand_spin.value()
        jpeg_quality = self._quality_spin.value()
        target_long_edge = self._res_combo.currentData() or 0
        model_key = self._model_combo.currentData() or ""

        # Preserve the source's subfolder layout under the output dir when
        # recursive scanning was used.
        src_root = src if recursive else None

        # If upscale requested with AI model, install deps first
        is_traditional = model_key.startswith("trad:")
        if target_long_edge > 0 and not is_traditional:
            from Imervue.gui.ai_upscale_dialog import REQUIRED_PACKAGES
            from Imervue.plugin.pip_installer import ensure_dependencies
            self._start_btn.setEnabled(False)
            self._status_label.setText(
                self._lang.get("upscale_installing",
                               "Installing dependencies..."))
            try:
                ensure_dependencies(
                    self._gui.main_window, REQUIRED_PACKAGES,
                    lambda: self._launch_worker(
                        paths, out, output_ext, rand_len, jpeg_quality,
                        target_long_edge, model_key, src_root))
            except Exception:
                logger.exception("ensure_dependencies failed")
                self._start_btn.setEnabled(True)
            return

        self._launch_worker(paths, out, output_ext, rand_len, jpeg_quality,
                            target_long_edge if is_traditional else 0,
                            model_key if is_traditional else "",
                            src_root)

    def _launch_worker(self, paths, out, output_ext, rand_len, jpeg_quality,
                       target_long_edge, model_key, src_root=None):
        self._start_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        if target_long_edge > 0:
            self._tile_progress.setValue(0)
            self._tile_progress.show()

        self._worker = _SanitizeWorker(
            paths, out, output_ext, rand_len, jpeg_quality, 6,
            target_long_edge, model_key, src_root, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.tile_progress.connect(self._on_tile_progress)
        self._worker.result_ready.connect(self._on_result)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._status_label.setText(
            self._lang.get("sanitize_processing", "Sanitizing: {name}")
            .replace("{name}", filename))

    def _on_tile_progress(self, done: int, total: int):
        self._tile_progress.setMaximum(total)
        self._tile_progress.setValue(done)

    def _on_result(self, success: int, failed: int):
        self._status_label.setText(
            self._lang.get("sanitize_done",
                           "Done — {success} sanitized, {failed} failed.")
            .replace("{success}", str(success))
            .replace("{failed}", str(failed)))

    def _on_finished(self):
        self._progress.hide()
        self._tile_progress.hide()
        self._start_btn.setEnabled(True)
        self._worker = None

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            with contextlib.suppress(RuntimeError, TypeError):
                self._worker.disconnect()
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


def open_image_sanitize(main_gui: GPUImageView) -> None:
    folder = None
    if hasattr(main_gui, "model") and hasattr(main_gui.model, "folder_path"):
        folder = main_gui.model.folder_path
    dlg = ImageSanitizeDialog(main_gui, folder)
    dlg.exec()
