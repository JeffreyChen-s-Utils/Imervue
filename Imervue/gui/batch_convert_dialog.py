"""
批次格式轉換
Batch Convert — one-click format conversion for entire folders or selections.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
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
    QSlider,
    QVBoxLayout,
)
from PIL import Image

from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.batch_convert")

_JPEG_EXT = ".jpeg"

FORMAT_OPTIONS = ["PNG", "JPEG", "WebP", "BMP", "TIFF"]
FORMAT_EXTENSIONS = {
    "PNG": ".png", "JPEG": ".jpg", "WebP": ".webp",
    "BMP": ".bmp", "TIFF": ".tiff",
}
QUALITY_FORMATS = {"JPEG", "WebP"}
_IMAGE_EXTS = frozenset({
    ".png", ".jpg", _JPEG_EXT, ".bmp", ".tiff", ".tif", ".webp",
    ".gif", ".apng",
})
_JPEG_EXTS = (".jpg", _JPEG_EXT)


def _scan_folder(folder: str) -> list[str]:
    result = []
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and Path(entry.name).suffix.lower() in _IMAGE_EXTS:
                result.append(entry.path)
    except OSError:
        pass
    result.sort(key=lambda p: os.path.basename(p).lower())
    return result


class _ConvertWorker(QThread):
    progress = Signal(int, int, str)  # current, total, filename
    result_ready = Signal(int, int, int)  # success, failed, skipped

    def __init__(self, paths: list[str], output_dir: str, fmt: str,
                 quality: int, delete_originals: bool, skip_same_fmt: bool):
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._fmt = fmt
        self._quality = quality
        self._delete_originals = delete_originals
        self._skip_same_fmt = skip_same_fmt

    def run(self):
        target_ext = FORMAT_EXTENSIONS.get(self._fmt, ".png")
        success = 0
        failed = 0
        skipped = 0
        total = len(self._paths)
        for i, src in enumerate(self._paths):
            self.progress.emit(i, total, Path(src).name)
            try:
                if self._should_skip(src, target_ext):
                    skipped += 1
                    continue
                self._convert_one(src, target_ext)
                success += 1
            except (OSError, ValueError) as exc:
                logger.error("Batch convert failed for %s: %s", src, exc)
                failed += 1
        self.result_ready.emit(success, failed, skipped)

    def _should_skip(self, src: str, target_ext: str) -> bool:
        if not self._skip_same_fmt:
            return False
        src_ext = Path(src).suffix.lower()
        if src_ext == target_ext:
            return True
        return src_ext in _JPEG_EXTS and target_ext in _JPEG_EXTS

    def _convert_one(self, src: str, target_ext: str) -> None:
        img = self._prepare_image(src)
        out_path = self._resolve_output_path(src, target_ext)
        kwargs = {"quality": self._quality} if self._fmt in QUALITY_FORMATS else {}
        img.save(str(out_path), format=self._fmt, **kwargs)
        self._maybe_delete_original(src, str(out_path))

    def _prepare_image(self, src: str) -> Image.Image:
        img = Image.open(src)
        needs_rgb = (
            (self._fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"))
            or (self._fmt == "BMP" and img.mode == "RGBA")
        )
        if needs_rgb:
            return img.convert("RGB")
        if img.mode not in ("RGB", "RGBA", "L"):
            return img.convert("RGBA")
        return img

    def _resolve_output_path(self, src: str, target_ext: str) -> Path:
        out_path = Path(self._output_dir) / (Path(src).stem + target_ext)
        if not (out_path.exists() and str(out_path) != src):
            return out_path
        counter = 1
        while out_path.exists():
            out_path = Path(self._output_dir) / f"{Path(src).stem}_{counter}{target_ext}"
            counter += 1
        return out_path

    def _maybe_delete_original(self, src: str, out_path: str) -> None:
        if not self._delete_originals:
            return
        if os.path.normpath(out_path) == os.path.normpath(src):
            return
        with contextlib.suppress(OSError):
            os.remove(src)


class BatchConvertDialog(QDialog):
    def __init__(self, main_gui: GPUImageView, paths: list[str] | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths: list[str] = paths or []
        self._lang = language_wrapper.language_word_dict
        self._worker = None

        self.setWindowTitle(
            self._lang.get("batch_convert_title", "Batch Format Conversion"))
        self.setMinimumWidth(500)
        self._build_ui()

        if self._paths:
            folder = str(Path(self._paths[0]).parent)
            self._src_edit.setText(folder)
            self._out_edit.setText(folder)
            self._update_count()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Source folder
        layout.addWidget(QLabel(
            self._lang.get("batch_convert_source", "Source folder:")))
        src_row = QHBoxLayout()
        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText(
            self._lang.get("batch_convert_source_hint",
                           "Choose a folder with images..."))
        src_browse = QPushButton(self._lang.get("export_browse", "Browse..."))
        src_browse.clicked.connect(self._browse_src)
        src_row.addWidget(self._src_edit, 1)
        src_row.addWidget(src_browse)
        layout.addLayout(src_row)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

        # Target format
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(
            self._lang.get("batch_convert_format", "Convert to:")))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(FORMAT_OPTIONS)
        self._fmt_combo.setCurrentText("WebP")
        self._fmt_combo.currentTextChanged.connect(self._on_format_changed)
        fmt_row.addWidget(self._fmt_combo, 1)
        layout.addLayout(fmt_row)

        # Quality
        self._quality_label = QLabel(
            self._lang.get("export_quality", "Quality:") + " 85")
        self._quality_slider = QSlider(Qt.Orientation.Horizontal)
        self._quality_slider.setRange(0, 100)
        self._quality_slider.setValue(85)
        self._quality_slider.valueChanged.connect(
            lambda v: self._quality_label.setText(
                self._lang.get("export_quality", "Quality:") + f" {v}")
        )
        layout.addWidget(self._quality_label)
        layout.addWidget(self._quality_slider)

        # Options
        self._skip_same = QCheckBox(
            self._lang.get("batch_convert_skip_same",
                           "Skip images already in target format"))
        self._skip_same.setChecked(True)
        layout.addWidget(self._skip_same)

        self._delete_orig = QCheckBox(
            self._lang.get("batch_convert_delete_orig",
                           "Delete original files after conversion"))
        self._delete_orig.setChecked(False)
        layout.addWidget(self._delete_orig)

        # Output folder
        self._same_dir_check = QCheckBox(
            self._lang.get("batch_convert_same_dir",
                           "Save to same folder as source"))
        self._same_dir_check.setChecked(True)
        self._same_dir_check.toggled.connect(self._on_same_dir_toggled)
        layout.addWidget(self._same_dir_check)

        self._out_label = QLabel(
            self._lang.get("batch_convert_output", "Output folder:"))
        self._out_label.setVisible(False)
        layout.addWidget(self._out_label)
        out_row = QHBoxLayout()
        self._out_edit = QLineEdit()
        self._out_edit.setVisible(False)
        self._out_browse = QPushButton(
            self._lang.get("export_browse", "Browse..."))
        self._out_browse.setVisible(False)
        self._out_browse.clicked.connect(self._browse_out)
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(self._out_browse)
        layout.addLayout(out_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton(
            self._lang.get("batch_convert_start", "Convert"))
        self._start_btn.clicked.connect(self._do_convert)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._start_btn)
        layout.addLayout(btn_row)

        self._on_format_changed()

    def _browse_src(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("batch_convert_source", "Source folder"))
        if folder:
            self._src_edit.setText(folder)
            self._paths = _scan_folder(folder)
            self._update_count()
            if self._same_dir_check.isChecked():
                self._out_edit.setText(folder)

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("batch_convert_output", "Output folder"))
        if folder:
            self._out_edit.setText(folder)

    def _update_count(self):
        count = len(self._paths)
        self._count_label.setText(
            self._lang.get("batch_convert_count",
                           "{count} image(s) found").format(count=count))
        self._start_btn.setEnabled(count > 0)

    def _on_format_changed(self, _text=None):
        visible = self._fmt_combo.currentText() in QUALITY_FORMATS
        self._quality_label.setVisible(visible)
        self._quality_slider.setVisible(visible)

    def _on_same_dir_toggled(self, checked):
        self._out_label.setVisible(not checked)
        self._out_edit.setVisible(not checked)
        self._out_browse.setVisible(not checked)

    def _do_convert(self):
        if not self._paths:
            return

        if self._same_dir_check.isChecked():
            output_dir = self._src_edit.text().strip()
        else:
            output_dir = self._out_edit.text().strip()
        if not output_dir:
            return
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        self._start_btn.setEnabled(False)
        self._progress.setMaximum(len(self._paths))
        self._progress.setValue(0)
        self._progress.setVisible(True)

        self._worker = _ConvertWorker(
            self._paths, output_dir,
            self._fmt_combo.currentText(),
            self._quality_slider.value(),
            self._delete_orig.isChecked(),
            self._skip_same.isChecked(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._cleanup)
        self._worker.start()

    def _on_progress(self, current, total, name):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {name}")

    def _cleanup(self):
        self._worker = None

    def _on_finished(self, success, failed, skipped):
        self._progress.setValue(len(self._paths))
        self._start_btn.setEnabled(True)

        msg = self._lang.get(
            "batch_convert_done",
            "Done — {success} converted, {skipped} skipped, {failed} failed."
        ).format(success=success, skipped=skipped, failed=failed)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)

        # Reload viewer if converted in-place
        if self._same_dir_check.isChecked():
            with contextlib.suppress(Exception):
                if self._gui.tile_grid_mode:
                    self._gui.load_tile_grid_async(list(self._gui.model.images))

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            with contextlib.suppress(RuntimeError, TypeError):
                self._worker.disconnect()
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


def open_batch_convert(main_gui: GPUImageView):
    """Open batch convert from current folder images."""
    paths = list(main_gui.model.images) if main_gui.model.images else None
    dlg = BatchConvertDialog(main_gui, paths=paths)
    dlg.exec()
