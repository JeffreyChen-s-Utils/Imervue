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

from Imervue.image.recipe_store import recipe_store
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


class _ExportWorker(QThread):
    progress = Signal(int, int)  # current, total
    result_ready = Signal(int, int)  # success, failed

    def __init__(self, paths, output_dir, fmt, quality, resize_enabled, max_w, max_h):
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._fmt = fmt
        self._quality = quality
        self._resize = resize_enabled
        self._max_w = max_w
        self._max_h = max_h

    def run(self):
        ext = FORMAT_EXTENSIONS.get(self._fmt, ".png")
        success = 0
        failed = 0
        total = len(self._paths)

        for i, src in enumerate(self._paths):
            try:
                img = _open_for_export(src)

                # 套用非破壞性 recipe — batch export 會把 develop panel 的調整烘進去。
                recipe = recipe_store.get_for_path(src)
                if recipe is not None and not recipe.is_identity():
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    arr = recipe.apply(np.array(img))
                    img = Image.fromarray(arr)

                # Resize
                if self._resize and (self._max_w > 0 or self._max_h > 0):
                    w, h = img.size
                    max_w = self._max_w if self._max_w > 0 else w
                    max_h = self._max_h if self._max_h > 0 else h
                    if w > max_w or h > max_h:
                        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

                # Mode conversion
                if self._fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                if self._fmt == "BMP" and img.mode == "RGBA":
                    img = img.convert("RGB")

                # Build output path
                out_name = Path(src).stem + ext
                out_path = Path(self._output_dir) / out_name
                # Avoid overwrite
                counter = 1
                while out_path.exists():
                    out_name = f"{Path(src).stem}_{counter}{ext}"
                    out_path = Path(self._output_dir) / out_name
                    counter += 1

                kwargs = {}
                if self._fmt in QUALITY_FORMATS:
                    kwargs["quality"] = self._quality

                img.save(str(out_path), format=self._fmt, **kwargs)
                success += 1
            except Exception as exc:
                logger.error(f"Batch export failed for {src}: {exc}")
                failed += 1

            self.progress.emit(i + 1, total)

        self.result_ready.emit(success, failed)


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

        self._worker = _ExportWorker(
            self._paths,
            output_dir,
            self._fmt_combo.currentText(),
            self._quality_slider.value(),
            self._resize_grp.isChecked(),
            self._max_w.value(),
            self._max_h.value(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

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
