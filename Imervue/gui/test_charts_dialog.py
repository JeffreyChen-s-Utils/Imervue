"""Test-chart generator dialog — synthesize a calibration pattern and save it.

Pure generation in :mod:`Imervue.image.test_charts`; this dialog picks a
pattern + size and writes the result to a chosen file.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.test_charts import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    PATTERNS,
    generate_chart,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.test_charts_dialog")

_MAX_DIM = 8192


class TestChartsDialog(QDialog):
    """Pick a pattern + dimensions and write a generated test chart."""

    def __init__(self, viewer: GPUImageView, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("testchart_title", "Test Chart"))
        self.setMinimumWidth(360)

        self._pattern = QComboBox()
        for pattern in PATTERNS:
            self._pattern.addItem(lang.get(f"testchart_{pattern}", pattern.title()), pattern)
        self._width = self._make_spin(DEFAULT_WIDTH)
        self._height = self._make_spin(DEFAULT_HEIGHT)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("testchart_pattern", "Pattern:")))
        layout.addWidget(self._pattern)
        layout.addWidget(QLabel(lang.get("testchart_width", "Width:")))
        layout.addWidget(self._width)
        layout.addWidget(QLabel(lang.get("testchart_height", "Height:")))
        layout.addWidget(self._height)
        layout.addLayout(self._build_buttons(lang))

    @staticmethod
    def _make_spin(value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, _MAX_DIM)
        spin.setValue(value)
        return spin

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        generate = QPushButton(lang.get("testchart_generate", "Generate & Save"))
        generate.clicked.connect(self._generate)
        row.addWidget(cancel)
        row.addWidget(generate)
        return row

    def _generate(self) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        out, _ = QFileDialog.getSaveFileName(
            self, lang.get("testchart_generate", "Generate & Save"),
            f"{self._pattern.currentData()}.png", "PNG (*.png)")
        if not out:
            return
        arr = generate_chart(self._pattern.currentData(),
                             self._width.value(), self._height.value())
        Image.fromarray(arr, mode="RGBA").save(out)
        toast = getattr(getattr(self._viewer, "main_window", None), "toast", None)
        if toast is not None:
            from pathlib import Path
            toast.info(lang.get("stats_exported", "Saved {path}").format(path=Path(out).name))
        self.accept()


def open_test_charts(viewer: GPUImageView) -> None:
    TestChartsDialog(viewer).exec()
