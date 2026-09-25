from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSlider, QPushButton, QMessageBox, QWidget,
)

from Imervue.gui.export_metadata_combo import metadata_row
from Imervue.gui.export_source import open_export_source
from Imervue.image.export_metadata import export_save_options
from Imervue.gui.dialog_rows import path_browse_row, save_path_into
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.image.save_formats import (
    FORMAT_EXTENSIONS,
    QUALITY_FORMATS,
    available_formats,
    save_image,
)
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.file_transfer import is_same_file
from Imervue.system.free_names import free_names
import contextlib

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.export_dialog")


class _SizeEstimateWorker(QThread):
    """Compute the in-memory output size for the chosen format off the UI thread."""
    result_ready = Signal(int, str)  # (size_bytes, error_message)

    def __init__(self, source_path: str, fmt: str, quality: int | None):
        super().__init__()
        self._source_path = source_path
        self._fmt = fmt
        self._quality = quality

    def run(self):
        try:
            import io
            img = open_export_source(self._source_path)
            buf = io.BytesIO()
            save_image(img, buf, self._fmt, self._quality)
            self.result_ready.emit(buf.tell(), "")
        except IMAGE_READ_ERRORS as exc:
            self.result_ready.emit(0, str(exc))
        except Exception as exc:
            # Worker boundary: the dialog waits on result_ready, so report even a bug.
            logger.exception("Estimating the export size of %s failed", self._source_path)
            self.result_ready.emit(0, str(exc))


def _ask_to_replace(parent: QWidget | None, text: str) -> bool:
    """Ask whether to replace an existing file; No is the default answer."""
    title = language_wrapper.language_word_dict.get("export_replace_title", "Replace File?")
    answer = QMessageBox.question(
        parent, title, text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No)
    return answer == QMessageBox.StandardButton.Yes


class ExportDialog(WorkerHostMixin, QDialog):
    """Dialog for exporting/converting images to different formats."""

    # The background file-size estimator; the mixin joins it on reject/close.
    _worker_attrs = ("_size_worker",)

    def __init__(self, source_path: str, parent=None):
        super().__init__(parent)
        self.source_path = source_path
        self._lang = language_wrapper.language_word_dict
        self._size_worker: _SizeEstimateWorker | None = None
        # The path last picked through Browse…: its Save dialog already asked
        # before picking an existing file.
        self._browsed_path: str | None = None

        self.setWindowTitle(self._lang.get("export_title", "Export Image"))
        self.setMinimumWidth(420)

        self._build_ui()
        self._connect_signals()
        self._update_quality_visibility()
        self._update_default_output_path()
        self._update_size_estimate()


    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Format row
        fmt_layout = QHBoxLayout()
        fmt_label = QLabel(self._lang.get("export_format", "Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(available_formats())
        fmt_layout.addWidget(fmt_label)
        fmt_layout.addWidget(self.format_combo, 1)
        layout.addLayout(fmt_layout)

        # Quality row
        self.quality_label = QLabel(self._lang.get("export_quality", "Quality:") + " 85")
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(0, 100)
        self.quality_slider.setValue(85)
        layout.addWidget(self.quality_label)
        layout.addWidget(self.quality_slider)

        metadata_layout, self.metadata_combo = metadata_row()
        layout.addLayout(metadata_layout)

        # Output path row
        path_layout, self.path_edit, _browse = path_browse_row(
            self._browse_output, browse_text=self._lang.get("export_browse", "Browse..."))
        self.path_edit.setPlaceholderText(
            self._lang.get("export_output_path_placeholder", "Output path"))
        layout.addLayout(path_layout)

        # Size estimate
        self.size_label = QLabel("")
        layout.addWidget(self.size_label)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton(self._lang.get("export_save", "Save"))
        self.save_btn.clicked.connect(self._do_export)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------ signals
    def _connect_signals(self) -> None:
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)

    def _on_format_changed(self, _text: str) -> None:
        self._update_quality_visibility()
        self._update_default_output_path()
        self._update_size_estimate()

    def _on_quality_changed(self, value: int) -> None:
        base_text = self._lang.get("export_quality", "Quality:")
        self.quality_label.setText(f"{base_text} {value}")
        self._update_size_estimate()

    # ----------------------------------------------------------- helpers
    def _selected_format(self) -> str:
        return self.format_combo.currentText()

    def _update_quality_visibility(self) -> None:
        visible = self._selected_format() in QUALITY_FORMATS
        self.quality_label.setVisible(visible)
        self.quality_slider.setVisible(visible)

    def _update_default_output_path(self) -> None:
        # A free name: the source's own name exported over the photo itself
        # (a PNG exported as PNG), and ``photo.png`` beside ``photo.jpg`` is
        # another picture.
        src = Path(self.source_path)
        ext = FORMAT_EXTENSIONS.get(self._selected_format(), ".png")
        self.path_edit.setText(str(free_names(src.parent, [src.stem], ext)[0]))

    def _update_size_estimate(self) -> None:
        """Kick off an async in-memory save to estimate output file size."""
        # Discard any in-flight worker — its result is now stale.
        if self._size_worker and self._size_worker.isRunning():
            with contextlib.suppress(TypeError, RuntimeError):
                self._size_worker.result_ready.disconnect(self._on_size_ready)

        self.size_label.setText(self._lang.get("export_size_calculating", "Calculating..."))

        fmt = self._selected_format()
        worker = _SizeEstimateWorker(self.source_path, fmt, self._quality_for(fmt))
        worker.result_ready.connect(self._on_size_ready)
        worker.finished.connect(lambda w=worker: w.deleteLater())
        self._size_worker = worker
        worker.start()

    def _on_size_ready(self, size_bytes: int, error: str) -> None:
        if error:
            self.size_label.setText("")
            return
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
        self.size_label.setText(f"~{size_str}")

    def _quality_for(self, fmt: str) -> int | None:
        return self.quality_slider.value() if fmt in QUALITY_FORMATS else None

    def _browse_output(self) -> None:
        fmt = self._selected_format()
        ext = FORMAT_EXTENSIONS.get(fmt, ".*")
        picked = save_path_into(
            self, self.path_edit, self._lang.get("export_save", "Save"), f"{fmt} (*{ext})")
        if picked:
            self._browsed_path = picked

    def _may_write(self, output_path: str) -> bool:
        """Whether writing *output_path* replaces nothing the user has not agreed to replace.

        Browse…'s Save dialog asks before picking an existing file; a typed path
        was never asked about. The photo being exported is asked about either
        way: the copy has its edits written into the pixels and keeps only the
        metadata chosen here.
        """
        if not os.path.exists(output_path):
            return True
        name = Path(output_path).name
        if is_same_file(output_path, self.source_path):
            text = self._lang.get(
                "export_replace_source",
                "“{name}” is the photo being exported. Replace the original with this "
                "copy? The copy has the photo's edits applied and keeps only the metadata "
                "chosen above.")
            return _ask_to_replace(self, text.format(name=name))
        if self._browsed_path and is_same_file(output_path, self._browsed_path):
            return True
        text = self._lang.get(
            "export_replace", "“{name}” already exists. Replace it?")
        return _ask_to_replace(self, text.format(name=name))

    # ------------------------------------------------------------ export
    def _do_export(self) -> None:
        output_path = self.path_edit.text().strip()
        if not output_path or not self._may_write(output_path):
            return

        fmt = self._selected_format()
        try:
            img = open_export_source(self.source_path)
            extra = export_save_options(self.source_path, self.metadata_combo.currentData())
            save_image(img, output_path, fmt, self._quality_for(fmt), extra)
            logger.info(f"Exported image to {output_path} as {fmt}")
            self.accept()
        except Exception as exc:
            logger.exception(f"Export failed: {exc}")


def open_export_dialog(main_gui: GPUImageView) -> None:
    """Open the export dialog for the currently viewed image."""
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return

    source_path = images[main_gui.current_index]
    if not os.path.isfile(source_path):
        return

    dialog = ExportDialog(source_path, parent=main_gui)
    dialog.exec()
