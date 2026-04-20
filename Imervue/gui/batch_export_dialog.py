"""
批次匯出
Batch export — convert, resize, and compress multiple images at once.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSlider, QPushButton, QFileDialog, QLineEdit, QSpinBox,
    QProgressBar, QGroupBox,
)
import numpy as np
from PIL import Image

from Imervue.image import export_presets
from Imervue.image.recipe_store import recipe_store
from Imervue.image.watermark import WatermarkOptions, apply_watermark
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.batch_export")

FORMAT_OPTIONS = ["PNG", "JPEG", "WebP", "BMP", "TIFF"]
FORMAT_EXTENSIONS = {
    "PNG": ".png", "JPEG": ".jpg", "WebP": ".webp",
    "BMP": ".bmp", "TIFF": ".tiff",
}
QUALITY_FORMATS = {"JPEG", "WebP"}


def _watermark_corners(lang):
    """Return (key, label) tuples for the watermark corner dropdown."""
    return [
        ("top-left", lang.get("watermark_tl", "Top-left")),
        ("top-right", lang.get("watermark_tr", "Top-right")),
        ("bottom-left", lang.get("watermark_bl", "Bottom-left")),
        ("bottom-right", lang.get("watermark_br", "Bottom-right")),
        ("center", lang.get("watermark_center", "Center")),
    ]


class _ExportWorker(QThread):
    progress = Signal(int, int)  # current, total
    result_ready = Signal(int, int)  # success, failed

    def __init__(
        self, paths, output_dir, fmt, quality, resize_enabled, max_w, max_h,
        square_crop: bool = False, dpi: int = 0,
        watermark: WatermarkOptions | None = None,
    ):
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._fmt = fmt
        self._quality = quality
        self._resize = resize_enabled
        self._max_w = max_w
        self._max_h = max_h
        self._square_crop = square_crop
        self._dpi = dpi
        self._watermark = watermark or WatermarkOptions()

    def run(self):
        success = failed = 0
        total = len(self._paths)
        for i, src in enumerate(self._paths):
            if self._process_one(src):
                success += 1
            else:
                failed += 1
            self.progress.emit(i + 1, total)
        self.result_ready.emit(success, failed)

    def _process_one(self, src: str) -> bool:
        try:
            img = _open_for_export(src)
            img = _apply_recipe(src, img)
            if self._square_crop:
                img = export_presets.square_crop(img)
            img = self._resize_if_needed(img)
            img = apply_watermark(img, self._watermark)
            img = _coerce_mode_for_format(img, self._fmt)
            out_path = _build_output_path(
                Path(src), self._output_dir, FORMAT_EXTENSIONS.get(self._fmt, ".png"),
            )
            img.save(str(out_path), format=self._fmt, **self._save_kwargs())
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Batch export failed for {src}: {exc}")
            return False

    def _resize_if_needed(self, img):
        if not self._resize or (self._max_w <= 0 and self._max_h <= 0):
            return img
        w, h = img.size
        max_w = self._max_w if self._max_w > 0 else w
        max_h = self._max_h if self._max_h > 0 else h
        if w > max_w or h > max_h:
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        return img

    def _save_kwargs(self) -> dict:
        kwargs: dict = {}
        if self._fmt in QUALITY_FORMATS:
            kwargs["quality"] = self._quality
        if self._dpi > 0:
            kwargs["dpi"] = (self._dpi, self._dpi)
        return kwargs


def _apply_recipe(src: str, img: Image.Image) -> Image.Image:
    """Bake the stored non-destructive recipe onto ``img`` if one exists."""
    recipe = recipe_store.get_for_path(src)
    if recipe is None or recipe.is_identity():
        return img
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return Image.fromarray(recipe.apply(np.array(img)))


def _coerce_mode_for_format(img: Image.Image, fmt: str) -> Image.Image:
    """Strip the alpha channel when the target format can't carry it."""
    if fmt == "JPEG" and img.mode in ("RGBA", "P"):
        return img.convert("RGB")
    if fmt == "BMP" and img.mode == "RGBA":
        return img.convert("RGB")
    return img


def _build_output_path(src: Path, output_dir: str, ext: str) -> Path:
    """Return a non-colliding output path for ``src`` inside ``output_dir``."""
    base = src.stem + ext
    out_path = Path(output_dir) / base
    counter = 1
    while out_path.exists():
        out_path = Path(output_dir) / f"{src.stem}_{counter}{ext}"
        counter += 1
    return out_path


class BatchExportDialog(QDialog):
    def __init__(self, main_gui: GPUImageView, paths: list[str]):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = paths
        self._lang = language_wrapper.language_word_dict
        self._worker = None

        self.setWindowTitle(self._lang.get("batch_export_title", "Batch Export"))
        self.setMinimumWidth(480)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # File count
        layout.addWidget(QLabel(
            self._lang.get("batch_export_count", "{count} image(s) selected").format(
                count=len(self._paths))
        ))

        # Presets
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel(
            self._lang.get("batch_export_preset", "Preset:")
        ))
        self._preset_combo = QComboBox()
        self._preset_combo.addItem(
            self._lang.get("batch_export_preset_custom", "Custom"), None,
        )
        for preset in export_presets.builtin_presets():
            self._preset_combo.addItem(preset.label, preset.key)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self._preset_combo, 1)
        layout.addLayout(preset_row)

        # Format
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(self._lang.get("export_format", "Format:")))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(FORMAT_OPTIONS)
        self._fmt_combo.currentTextChanged.connect(self._on_format_changed)
        fmt_row.addWidget(self._fmt_combo, 1)
        layout.addLayout(fmt_row)

        # Quality
        self._quality_label = QLabel(self._lang.get("export_quality", "Quality:") + " 85")
        self._quality_slider = QSlider(Qt.Orientation.Horizontal)
        self._quality_slider.setRange(0, 100)
        self._quality_slider.setValue(85)
        self._quality_slider.valueChanged.connect(
            lambda v: self._quality_label.setText(
                self._lang.get("export_quality", "Quality:") + f" {v}")
        )
        layout.addWidget(self._quality_label)
        layout.addWidget(self._quality_slider)

        # Resize
        resize_grp = QGroupBox(self._lang.get("batch_export_resize", "Resize"))
        resize_grp.setCheckable(True)
        resize_grp.setChecked(False)
        self._resize_grp = resize_grp
        rlay = QHBoxLayout(resize_grp)
        rlay.addWidget(QLabel(self._lang.get("batch_export_max_width", "Max Width:")))
        self._max_w = QSpinBox()
        self._max_w.setRange(0, 99999)
        self._max_w.setValue(1920)
        self._max_w.setSpecialValueText("--")
        rlay.addWidget(self._max_w)
        rlay.addWidget(QLabel(self._lang.get("batch_export_max_height", "Max Height:")))
        self._max_h = QSpinBox()
        self._max_h.setRange(0, 99999)
        self._max_h.setValue(1080)
        self._max_h.setSpecialValueText("--")
        rlay.addWidget(self._max_h)
        layout.addWidget(resize_grp)

        # Watermark
        wm_grp = QGroupBox(self._lang.get("watermark_title", "Watermark"))
        wm_grp.setCheckable(True)
        wm_grp.setChecked(False)
        self._wm_grp = wm_grp
        wm_layout = QVBoxLayout(wm_grp)
        wm_text_row = QHBoxLayout()
        wm_text_row.addWidget(QLabel(self._lang.get("watermark_text", "Text:")))
        self._wm_text = QLineEdit()
        self._wm_text.setPlaceholderText("\u00a9 Your name")
        wm_text_row.addWidget(self._wm_text, 1)
        wm_layout.addLayout(wm_text_row)
        wm_opts_row = QHBoxLayout()
        wm_opts_row.addWidget(QLabel(self._lang.get("watermark_position", "Position:")))
        self._wm_corner = QComboBox()
        for corner_key, corner_label in _watermark_corners(self._lang):
            self._wm_corner.addItem(corner_label, corner_key)
        self._wm_corner.setCurrentIndex(3)  # bottom-right
        wm_opts_row.addWidget(self._wm_corner)
        wm_opts_row.addWidget(QLabel(self._lang.get("watermark_opacity", "Opacity:")))
        self._wm_opacity = QSlider(Qt.Orientation.Horizontal)
        self._wm_opacity.setRange(10, 100)
        self._wm_opacity.setValue(60)
        wm_opts_row.addWidget(self._wm_opacity, 1)
        wm_layout.addLayout(wm_opts_row)
        layout.addWidget(wm_grp)

        # Output dir
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        if self._paths:
            self._dir_edit.setText(str(Path(self._paths[0]).parent))
        browse_btn = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._export_btn = QPushButton(self._lang.get("batch_export_start", "Export"))
        self._export_btn.clicked.connect(self._do_export)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._export_btn)
        layout.addLayout(btn_row)

        self._on_format_changed()

    def _on_format_changed(self, _text=None):
        visible = self._fmt_combo.currentText() in QUALITY_FORMATS
        self._quality_label.setVisible(visible)
        self._quality_slider.setVisible(visible)

    def _on_preset_changed(self, _index: int) -> None:
        """Apply the selected preset's values into the UI controls."""
        key = self._preset_combo.currentData()
        if not key:
            return
        preset = export_presets.get_preset(key)
        if preset is None:
            return
        self._fmt_combo.setCurrentText(preset.format)
        self._quality_slider.setValue(preset.quality)
        resize_on = preset.max_width > 0 or preset.max_height > 0
        self._resize_grp.setChecked(resize_on)
        if resize_on:
            self._max_w.setValue(preset.max_width)
            self._max_h.setValue(preset.max_height)
        self._active_preset = preset

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._dir_edit.setText(folder)

    def _do_export(self):
        output_dir = self._dir_edit.text().strip()
        if not output_dir or not Path(output_dir).is_dir():
            return

        self._export_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._paths))
        self._progress.setValue(0)

        preset = getattr(self, "_active_preset", None)
        preset_active = self._preset_combo.currentData() is not None
        self._worker = _ExportWorker(
            self._paths,
            output_dir,
            self._fmt_combo.currentText(),
            self._quality_slider.value(),
            self._resize_grp.isChecked(),
            self._max_w.value(),
            self._max_h.value(),
            square_crop=preset.square_crop if preset_active and preset else False,
            dpi=preset.dpi if preset_active and preset else 0,
            watermark=self._collect_watermark(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _collect_watermark(self) -> WatermarkOptions:
        """Read the watermark group's current controls into a value object."""
        if not self._wm_grp.isChecked() or not self._wm_text.text().strip():
            return WatermarkOptions()
        return WatermarkOptions(
            text=self._wm_text.text().strip(),
            corner=self._wm_corner.currentData() or "bottom-right",
            opacity=self._wm_opacity.value() / 100.0,
        )

    def _on_progress(self, current, total):
        self._progress.setValue(current)
        self._status_label.setText(f"{current}/{total}")

    def _cleanup_worker(self):
        self._worker = None

    def _on_finished(self, success, failed):
        self._progress.setVisible(False)
        self._export_btn.setEnabled(True)

        msg = self._lang.get(
            "batch_export_done", "Exported {success}/{total} image(s)"
        ).format(success=success, total=success + failed)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)

        QTimer.singleShot(0, self.accept)


def _open_for_export(path: str) -> Image.Image:
    if Path(path).suffix.lower() == ".svg":
        from Imervue.gpu_image_view.images.image_loader import _load_svg
        arr = _load_svg(path, thumbnail=False)
        return Image.fromarray(arr)
    return Image.open(path)


def open_batch_export(main_gui: GPUImageView):
    paths = list(main_gui.selected_tiles)
    if not paths:
        return
    dlg = BatchExportDialog(main_gui, paths)
    dlg.exec()
