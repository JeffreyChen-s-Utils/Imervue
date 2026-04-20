"""Auto-straighten dialog — detect the horizon angle and preview the result."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal
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
    QVBoxLayout,
)

from Imervue.image.auto_straighten import detect_horizon_angle
from Imervue.image.geometry import straighten
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.auto_straighten_dialog")


class _DetectWorker(QThread):
    done = Signal(bool, float)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self):
        try:
            arr = np.asarray(Image.open(self._path).convert("RGBA"))
            angle = detect_horizon_angle(arr)
            self.done.emit(True, float(angle))
        except (OSError, ValueError, RuntimeError) as exc:
            logger.error("Auto-straighten detect failed: %s", exc, exc_info=True)
            self.done.emit(False, 0.0)


class _ApplyWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, src: str, out: str, angle: float):
        super().__init__()
        self._src = src
        self._out = out
        self._angle = angle

    def run(self):
        try:
            arr = np.asarray(Image.open(self._src).convert("RGBA"))
            out = straighten(arr, self._angle)
            Image.fromarray(out).save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError, RuntimeError) as exc:
            logger.error("Auto-straighten apply failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class AutoStraightenDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        self._worker = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("autostr_title", "Auto-Straighten"))
        self.setMinimumWidth(420)

        self._angle = QDoubleSpinBox()
        self._angle.setRange(-45.0, 45.0)
        self._angle.setDecimals(2)
        self._angle.setSingleStep(0.1)

        detect_btn = QPushButton(lang.get("autostr_detect", "Detect angle"))
        detect_btn.clicked.connect(self._detect)

        angle_row = QHBoxLayout()
        angle_row.addWidget(self._angle, 1)
        angle_row.addWidget(detect_btn)

        form = QFormLayout()
        form.addRow(lang.get("autostr_angle", "Rotation (°):"), angle_row)

        self._out_edit = QLineEdit(self._default_output_path())
        browse = QPushButton(lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._pick_out)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("autostr_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(browse)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("autostr_apply", "Apply"))
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    def _default_output_path(self) -> str:
        p = Path(self._path)
        return str(p.with_name(f"{p.stem}_straight{p.suffix or '.png'}"))

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("autostr_output", "Output"), self._out_edit.text(),
            "Images (*.png *.jpg *.tif)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _detect(self) -> None:
        self._progress.setVisible(True)
        self._worker = _DetectWorker(self._path)
        self._worker.done.connect(self._on_detect_done)
        self._worker.start()

    def _on_detect_done(self, ok: bool, angle: float) -> None:
        self._progress.setVisible(False)
        if ok:
            self._angle.setValue(float(angle))

    def _apply(self) -> None:
        out = self._out_edit.text().strip()
        if not out:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _ApplyWorker(self._path, out, self._angle.value())
        self._worker.done.connect(self._on_apply_done)
        self._worker.start()

    def _on_apply_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_auto_straighten(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    AutoStraightenDialog(viewer, str(path)).exec()
