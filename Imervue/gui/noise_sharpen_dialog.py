"""Noise reduction + sharpening dialog."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from Imervue.image.denoise import reduce_noise, sharpen
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.noise_sharpen_dialog")

_SLIDER_STEPS = 100


class _Worker(QThread):
    done = Signal(bool, str)

    def __init__(self, src: str, out: str, nr_strength: float,
                 luma_only: bool, sharp_amount: float, sharp_radius: float):
        super().__init__()
        self._src = src
        self._out = out
        self._nr_strength = nr_strength
        self._luma_only = luma_only
        self._sharp_amount = sharp_amount
        self._sharp_radius = sharp_radius

    def run(self):
        try:
            arr = np.asarray(Image.open(self._src).convert("RGBA"))
            if self._nr_strength > 1e-4:
                arr = reduce_noise(
                    arr, self._nr_strength, preserve_color=not self._luma_only,
                )
            if self._sharp_amount > 1e-4:
                arr = sharpen(arr, self._sharp_amount, self._sharp_radius)
            Image.fromarray(arr).save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError, RuntimeError) as exc:
            logger.error("Denoise/sharpen failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class NoiseSharpenDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        self._worker: _Worker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("nr_title", "Noise Reduction / Sharpening"))
        self.setMinimumWidth(460)

        self._nr_strength = self._make_slider(0, _SLIDER_STEPS, 0)
        self._luma_only = QCheckBox(lang.get("nr_luma_only", "Luminance only"))
        self._sharp_amount = self._make_slider(0, 3 * _SLIDER_STEPS, 0)
        self._sharp_radius = self._make_slider(1, 5 * _SLIDER_STEPS, 150)

        form = QFormLayout()
        form.addRow(lang.get("nr_strength", "NR strength:"), self._nr_strength)
        form.addRow("", self._luma_only)
        form.addRow(lang.get("nr_sharpen_amount", "Sharpen amount:"),
                    self._sharp_amount)
        form.addRow(lang.get("nr_sharpen_radius", "Sharpen radius (px):"),
                    self._sharp_radius)

        self._out_edit = QLineEdit(self._default_output_path())
        browse = QPushButton(lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._pick_out)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("nr_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(browse)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("nr_run", "Apply"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    @staticmethod
    def _make_slider(minimum: int, maximum: int, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(minimum, maximum)
        s.setValue(value)
        return s

    def _default_output_path(self) -> str:
        p = Path(self._path)
        return str(p.with_name(f"{p.stem}_nr{p.suffix or '.png'}"))

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("nr_output", "Output"), self._out_edit.text(),
            "Images (*.png *.jpg *.tif)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _run(self) -> None:
        out = self._out_edit.text().strip()
        if not out:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        nr = self._nr_strength.value() / _SLIDER_STEPS
        amt = self._sharp_amount.value() / _SLIDER_STEPS
        rad = max(0.1, self._sharp_radius.value() / _SLIDER_STEPS)
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _Worker(
            self._path, out, nr, self._luma_only.isChecked(), amt, rad,
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_noise_sharpen(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    NoiseSharpenDialog(viewer, str(path)).exec()
