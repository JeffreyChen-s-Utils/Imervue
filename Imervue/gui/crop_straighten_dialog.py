"""Crop / straighten / perspective dialog.

Combines three related geometric edits in one dialog. The crop inputs are
normalised fractions so they round-trip with ``Recipe.crop`` regardless of
the source resolution; straighten writes a new output file because it
rotates by an arbitrary angle (not a quarter turn like ``Recipe.rotate_steps``).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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

from Imervue.image.geometry import CropRect, apply_crop, straighten
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.crop_straighten_dialog")

_ANGLE_SLIDER_STEPS = 150   # ±15° in 0.1° increments


class _Worker(QThread):
    done = Signal(bool, str)

    def __init__(self, src: str, out: str, angle: float, rect: CropRect | None):
        super().__init__()
        self._src = src
        self._out = out
        self._angle = angle
        self._rect = rect

    def run(self):
        try:
            arr = np.asarray(Image.open(self._src).convert("RGBA"))
            if abs(self._angle) > 1e-4:
                arr = straighten(arr, self._angle)
            if self._rect is not None:
                arr = apply_crop(arr, self._rect)
            Image.fromarray(arr).save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError, RuntimeError) as exc:
            logger.error("Crop/straighten failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class CropStraightenDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        self._worker: _Worker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("crop_title", "Crop / Straighten"))
        self.setMinimumWidth(460)

        self._angle = QSlider(Qt.Orientation.Horizontal)
        self._angle.setRange(-_ANGLE_SLIDER_STEPS, _ANGLE_SLIDER_STEPS)
        self._angle.setValue(0)
        self._angle_label = QLabel("0.0°")
        self._angle.valueChanged.connect(self._update_angle_label)

        self._crop_x = self._make_spin(0.0, 1.0, 0.0)
        self._crop_y = self._make_spin(0.0, 1.0, 0.0)
        self._crop_w = self._make_spin(0.05, 1.0, 1.0)
        self._crop_h = self._make_spin(0.05, 1.0, 1.0)

        form = QFormLayout()
        angle_row = QHBoxLayout()
        angle_row.addWidget(self._angle, 1)
        angle_row.addWidget(self._angle_label)
        form.addRow(lang.get("crop_angle", "Straighten angle:"), angle_row)
        form.addRow(lang.get("crop_x", "Crop X (0..1):"), self._crop_x)
        form.addRow(lang.get("crop_y", "Crop Y (0..1):"), self._crop_y)
        form.addRow(lang.get("crop_w", "Crop width (0..1):"), self._crop_w)
        form.addRow(lang.get("crop_h", "Crop height (0..1):"), self._crop_h)

        self._out_edit = QLineEdit(self._default_output_path())
        browse = QPushButton(lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._pick_out)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("crop_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(browse)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("crop_run", "Apply"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    @staticmethod
    def _make_spin(minimum: float, maximum: float, value: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(minimum, maximum)
        s.setSingleStep(0.05)
        s.setDecimals(3)
        s.setValue(value)
        return s

    def _update_angle_label(self, v: int) -> None:
        self._angle_label.setText(f"{v / 10.0:.1f}°")

    def _default_output_path(self) -> str:
        p = Path(self._path)
        return str(p.with_name(f"{p.stem}_crop{p.suffix or '.png'}"))

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("crop_output", "Output"), self._out_edit.text(),
            "Images (*.png *.jpg *.tif)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _run(self) -> None:
        out = self._out_edit.text().strip()
        if not out:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        angle = self._angle.value() / 10.0
        rect = CropRect(
            x=self._crop_x.value(), y=self._crop_y.value(),
            w=self._crop_w.value(), h=self._crop_h.value(),
        )
        use_rect = (
            rect.x > 0.001 or rect.y > 0.001
            or rect.w < 0.999 or rect.h < 0.999
        )
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _Worker(self._path, out, angle, rect if use_rect else None)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_crop_straighten(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    CropStraightenDialog(viewer, str(path)).exec()
