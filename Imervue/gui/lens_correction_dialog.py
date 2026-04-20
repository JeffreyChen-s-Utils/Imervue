"""
Lens correction dialog.

Exposes four pure-numpy lens-correction sliders: radial distortion
(``k1``), vignette lift, and chromatic-aberration red/blue scale offsets.
The corrected image is written to a user-chosen output path.
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

from Imervue.image.lens_correction import LensCorrectionOptions, apply_lens_correction
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.lens_correction_dialog")

_SLIDER_RANGE = 100          # logical slider steps
_K1_MAX = 0.4                # ±0.4 covers most real lens distortion
_VIGNETTE_MAX = 1.0          # ±1 corner lift range
_CA_MAX = 0.02               # ±2% per-channel radial scale offset


class _LensWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, src: str, out_path: str, opts: LensCorrectionOptions):
        super().__init__()
        self._src = src
        self._out = out_path
        self._opts = opts

    def run(self):
        try:
            arr = np.asarray(Image.open(self._src).convert("RGBA"))
            result = apply_lens_correction(arr, self._opts)
            Image.fromarray(result).save(self._out)
            self.done.emit(True, self._out)
        except Exception as exc:
            logger.error("Lens correction failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class LensCorrectionDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        self._worker: _LensWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("lens_title", "Lens Correction"))
        self.setMinimumWidth(480)

        self._k1 = self._make_slider()
        self._vignette = self._make_slider()
        self._ca_red = self._make_slider()
        self._ca_blue = self._make_slider()

        form = QFormLayout()
        form.addRow(
            lang.get("lens_k1", "Distortion (barrel / pincushion):"), self._k1)
        form.addRow(
            lang.get("lens_vignette", "Vignette correction:"), self._vignette)
        form.addRow(
            lang.get("lens_ca_red", "Chromatic aberration (red):"), self._ca_red)
        form.addRow(
            lang.get("lens_ca_blue", "Chromatic aberration (blue):"), self._ca_blue)

        self._out_edit = QLineEdit(self._default_output_path())
        out_browse = QPushButton(lang.get("export_browse", "Browse..."))
        out_browse.clicked.connect(self._pick_out)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("lens_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(out_browse)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("lens_run", "Apply"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    def _make_slider(self) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(-_SLIDER_RANGE, _SLIDER_RANGE)
        s.setValue(0)
        return s

    def _default_output_path(self) -> str:
        p = Path(self._path)
        return str(p.with_name(f"{p.stem}_lens{p.suffix or '.png'}"))

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("lens_output", "Output"), self._out_edit.text(),
            "Images (*.png *.jpg *.tif)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _scaled(self, slider: QSlider, max_val: float) -> float:
        return slider.value() / _SLIDER_RANGE * max_val

    def _run(self) -> None:
        out = self._out_edit.text().strip()
        if not out:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        opts = LensCorrectionOptions(
            k1=self._scaled(self._k1, _K1_MAX),
            vignette=self._scaled(self._vignette, _VIGNETTE_MAX),
            ca_red=self._scaled(self._ca_red, _CA_MAX),
            ca_blue=self._scaled(self._ca_blue, _CA_MAX),
        )
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _LensWorker(self._path, out, opts)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_lens_correction(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    LensCorrectionDialog(viewer, str(path)).exec()
