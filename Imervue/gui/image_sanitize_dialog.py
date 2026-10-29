"""
圖片淨化重繪工具
Image Sanitizer — losslessly re-render images from raw pixel data,
stripping ALL hidden data (metadata, EXIF, steganography, trailing
bytes, alternate streams) and renaming with date + random string.

Optionally upscale to a common target resolution using AI (Real-ESRGAN)
or traditional resampling methods (Lanczos, Bicubic, Nearest) while
keeping aspect ratio.

The Qt-free pipeline lives in :mod:`Imervue.gui.image_sanitize_core` and the
background thread in :mod:`Imervue.gui.image_sanitize_worker`; this module
holds the dialog and keeps re-exporting both so existing imports still work.
"""
from __future__ import annotations

import logging
import os
from dataclasses import replace
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.gui.dialog_rows import folder_picker_row
from Imervue.gui.image_sanitize_core import (
    _IMAGE_EXTS,
    _LSB_SCRAMBLE_RATE,
    _PIL_FORMAT_MAP,
    _EXT_BMP,
    _EXT_JPG,
    _EXT_PNG,
    _EXT_TIFF,
    _EXT_WEBP,
    TARGET_RESOLUTIONS,
    SanitizeSettings,
    UpscaleSpec,
    _ai_upscale,
    _allocate_output_path,
    _compute_upscale_params,
    _final_dims,
    _generate_name,
    _get_image_date,
    _make_unseeded_rng,
    _maybe_upscale,
    _resolve_output_ext,
    _save_kwargs_for,
    _scan_folder,
    _scramble_lsb,
    sanitize_image,
)
from Imervue.gui.image_sanitize_worker import _SanitizeWorker
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.ui_scale import font_px

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.image_sanitize")

# The pipeline and worker names stay importable from here (callers, tests).
__all__ = [
    "TARGET_RESOLUTIONS",
    "ImageSanitizeDialog",
    "SanitizeSettings",
    "UpscaleSpec",
    "_IMAGE_EXTS",
    "_LSB_SCRAMBLE_RATE",
    "_PIL_FORMAT_MAP",
    "_SanitizeWorker",
    "_ai_upscale",
    "_allocate_output_path",
    "_compute_upscale_params",
    "_final_dims",
    "_generate_name",
    "_get_image_date",
    "_make_unseeded_rng",
    "_maybe_upscale",
    "_resolve_output_ext",
    "_save_kwargs_for",
    "_scan_folder",
    "_scramble_lsb",
    "open_image_sanitize",
    "sanitize_image",
]

# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class ImageSanitizeDialog(WorkerHostMixin, QDialog):
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

        src_row, self._src_edit = folder_picker_row(
            lang.get("sanitize_source", "Source folder:"), self._browse_src)
        layout.addLayout(src_row)

        self._recursive_check = QCheckBox(
            lang.get("duplicate_recursive", "Include subfolders"))
        layout.addWidget(self._recursive_check)

        out_row, self._out_edit = folder_picker_row(
            lang.get("organizer_output", "Output folder:"), self._browse_out)
        layout.addLayout(out_row)

        layout.addLayout(self._build_format_row())

        rand_row, self._rand_spin = self._spin_row(
            lang.get("sanitize_rand_len", "Random string length:"), 4, 32, 8)
        layout.addLayout(rand_row)

        quality_row, self._quality_spin = self._spin_row(
            lang.get("sanitize_jpeg_quality", "JPEG quality:"), 1, 100, 95)
        layout.addLayout(quality_row)

        layout.addWidget(self._build_upscale_group())

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
        layout.addLayout(self._build_button_row())

    @staticmethod
    def _spin_row(label: str, minimum: int, maximum: int,
                  value: int) -> tuple[QHBoxLayout, QSpinBox]:
        """Label and a left-aligned spin box with the given range and start value."""
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        row.addWidget(spin)
        row.addStretch()
        return row, spin

    def _build_format_row(self) -> QHBoxLayout:
        """Output-format combo: "same as source" followed by the fixed formats."""
        lang = self._lang
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(
            lang.get("sanitize_output_format", "Output format:")))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItem(
            lang.get("sanitize_fmt_same", "Same as source"), "same")
        self._fmt_combo.addItem("PNG (.png)", _EXT_PNG)
        self._fmt_combo.addItem("JPEG (.jpg)", _EXT_JPG)
        self._fmt_combo.addItem("WebP (.webp)", _EXT_WEBP)
        self._fmt_combo.addItem("BMP (.bmp)", _EXT_BMP)
        self._fmt_combo.addItem("TIFF (.tiff)", _EXT_TIFF)
        fmt_row.addWidget(self._fmt_combo, 1)
        return fmt_row

    def _build_upscale_group(self) -> QGroupBox:
        """Target-resolution and model combos with the hint that tracks them."""
        lang = self._lang
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
        from Imervue.gui.ai_upscale_dialog import fill_upscale_model_combo
        fill_upscale_model_combo(self._model_combo, lang)
        model_row.addWidget(self._model_combo, 1)
        upscale_layout.addLayout(model_row)

        # Auto-select model hint
        self._model_hint = QLabel("")
        self._model_hint.setStyleSheet(f"color: gray; {font_px(11)}")
        upscale_layout.addWidget(self._model_hint)
        self._res_combo.currentIndexChanged.connect(self._on_res_changed)
        self._on_res_changed()
        return upscale_group

    def _build_button_row(self) -> QHBoxLayout:
        """Start on the left, Close on the right."""
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton(self._lang.get("organizer_start", "Start"))
        self._start_btn.clicked.connect(self._do_start)
        btn_row.addWidget(self._start_btn)
        btn_row.addStretch()
        close_btn = QPushButton(self._lang.get("export_cancel", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        return btn_row

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

        settings = SanitizeSettings(output_ext, rand_len=rand_len, jpeg_quality=jpeg_quality,
                                    target_long_edge=target_long_edge, model_key=model_key)
        # If upscale requested with AI model, install deps first
        is_traditional = model_key.startswith("trad:")
        if target_long_edge > 0 and not is_traditional:
            from Imervue.gui.ai_upscale_dialog import REQUIRED_PACKAGES
            from Imervue.plugin.pip_installer import ensure_dependencies
            # Don't disable Start here — ensure_dependencies only calls on_ready on
            # a successful install, so disabling now would strand the button if
            # the user cancels the install prompt. _launch_worker disables it once
            # the work actually starts.
            self._status_label.setText(
                self._lang.get("upscale_installing",
                               "Installing dependencies..."))
            try:
                ensure_dependencies(
                    self._gui.main_window, REQUIRED_PACKAGES,
                    lambda: self._launch_worker(paths, out, settings, src_root=src_root))
            except Exception:
                logger.exception("ensure_dependencies failed")
                self._start_btn.setEnabled(True)
            return

        if not is_traditional:   # no upscale requested (target 0): drop the model choice
            settings = replace(settings, target_long_edge=0, model_key="")
        self._launch_worker(paths, out, settings, src_root=src_root)

    def _launch_worker(self, paths: list[str], out: str, settings: SanitizeSettings, *,
                       src_root: str | None = None) -> None:
        self._start_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        if settings.target_long_edge > 0:
            self._tile_progress.setValue(0)
            self._tile_progress.show()

        self._worker = _SanitizeWorker(paths, out, settings, src_root=src_root, parent=self)
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


def open_image_sanitize(main_gui: GPUImageView) -> None:
    folder = None
    if hasattr(main_gui, "model") and hasattr(main_gui.model, "folder_path"):
        folder = main_gui.model.folder_path
    dlg = ImageSanitizeDialog(main_gui, folder)
    dlg.exec()
