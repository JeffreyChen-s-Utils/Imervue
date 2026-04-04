from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSlider, QPushButton, QFileDialog, QLineEdit,
)
from PIL import Image

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.export_dialog")

# Supported export formats and their PIL save parameters
FORMAT_OPTIONS: list[str] = ["PNG", "JPEG", "WebP", "BMP", "TIFF"]
FORMAT_EXTENSIONS: dict[str, str] = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WebP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
}
# Formats that support a quality parameter
QUALITY_FORMATS: set[str] = {"JPEG", "WebP"}


class ExportDialog(QDialog):
    """Dialog for exporting/converting images to different formats."""

    def __init__(self, source_path: str, parent=None):
        super().__init__(parent)
        self.source_path = source_path
        self._lang = language_wrapper.language_word_dict

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
        self.format_combo.addItems(FORMAT_OPTIONS)
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

        # Output path row
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Output path")
        browse_btn = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse_output)
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(browse_btn)
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
        src = Path(self.source_path)
        ext = FORMAT_EXTENSIONS.get(self._selected_format(), ".png")
        default_name = src.stem + ext
        default_path = src.parent / default_name
        self.path_edit.setText(str(default_path))

    def _update_size_estimate(self) -> None:
        """Show a rough file-size estimate by doing an in-memory save."""
        try:
            import io
            img = _open_image_for_export(self.source_path)
            buf = io.BytesIO()
            fmt = self._selected_format()
            save_kwargs = self._build_save_kwargs(fmt)
            # Convert mode if needed for formats that don't support alpha
            if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(buf, format=fmt, **save_kwargs)
            size_bytes = buf.tell()
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            self.size_label.setText(f"~{size_str}")
        except Exception:
            self.size_label.setText("")

    def _build_save_kwargs(self, fmt: str) -> dict:
        kwargs: dict = {}
        if fmt in QUALITY_FORMATS:
            kwargs["quality"] = self.quality_slider.value()
        return kwargs

    def _browse_output(self) -> None:
        fmt = self._selected_format()
        ext = FORMAT_EXTENSIONS.get(fmt, ".*")
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._lang.get("export_save", "Save"),
            self.path_edit.text(),
            f"{fmt} (*{ext})",
        )
        if path:
            self.path_edit.setText(path)

    # ------------------------------------------------------------ export
    def _do_export(self) -> None:
        output_path = self.path_edit.text().strip()
        if not output_path:
            return

        fmt = self._selected_format()
        save_kwargs = self._build_save_kwargs(fmt)

        try:
            img = _open_image_for_export(self.source_path)
            # Convert mode if the target format doesn't support the current mode
            if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            if fmt == "BMP" and img.mode == "RGBA":
                img = img.convert("RGB")

            img.save(output_path, format=fmt, **save_kwargs)
            logger.info(f"Exported image to {output_path} as {fmt}")
            self.accept()
        except Exception as exc:
            logger.error(f"Export failed: {exc}")


def _open_image_for_export(path: str) -> Image.Image:
    """Open an image file for export, handling SVG via QSvgRenderer."""
    if Path(path).suffix.lower() == ".svg":
        from Imervue.gpu_image_view.images.image_loader import _load_svg
        import numpy as np
        arr = _load_svg(path, thumbnail=False)
        return Image.fromarray(arr)
    return Image.open(path)


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
