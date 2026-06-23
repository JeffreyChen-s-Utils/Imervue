"""Solarize dialog — apply a tone reversal to the current image and save a copy.

Pure math in :mod:`Imervue.image.solarize`; this is the Qt shell (threshold and
mix sliders, background worker) following the shared apply-and-save pattern.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
)
from Imervue.image.solarize import apply_solarize
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.solarize_dialog")

_PERCENT = 100.0
_DEFAULT_THRESHOLD = 50
_DEFAULT_MIX = 100


class _SolarizeWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, threshold: float, mix: float, out_path: str):
        super().__init__()
        self._path = path
        self._threshold = threshold
        self._mix = mix
        self._out = out_path

    def run(self) -> None:
        try:
            result = apply_solarize(load_rgba(self._path), self._threshold, self._mix)
            Image.fromarray(result, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Solarize failed: %s", exc)
            self.done.emit(False, str(exc))


class SolarizeDialog(QDialog):
    """Threshold + mix sliders that solarize the current image and save a copy."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _SolarizeWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("solarize_title", "Solarize"))
        self.setMinimumWidth(360)

        self._threshold = self._make_slider(_DEFAULT_THRESHOLD)
        self._threshold_label = QLabel(str(_DEFAULT_THRESHOLD))
        self._threshold.valueChanged.connect(
            lambda v: self._threshold_label.setText(str(v)),
        )
        self._mix = self._make_slider(_DEFAULT_MIX)
        self._mix_label = QLabel(str(_DEFAULT_MIX))
        self._mix.valueChanged.connect(lambda v: self._mix_label.setText(str(v)))

        form = QFormLayout()
        form.addRow(
            lang.get("solarize_threshold", "Threshold (%):"),
            _slider_row(self._threshold, self._threshold_label),
        )
        form.addRow(
            lang.get("solarize_mix", "Mix (%):"),
            _slider_row(self._mix, self._mix_label),
        )
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    @staticmethod
    def _make_slider(value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, int(_PERCENT))
        slider.setValue(value)
        return slider

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_solarize.png")
        self._worker = _SolarizeWorker(
            self._path,
            self._threshold.value() / _PERCENT,
            self._mix.value() / _PERCENT,
            str(out_path),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "solarize_failed", "Solarize failed")
        if ok:
            self.accept()


def _slider_row(slider: QSlider, label: QLabel) -> QWidget:
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(slider, stretch=1)
    label.setMinimumWidth(36)
    row.addWidget(label)
    return container


def open_solarize(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        SolarizeDialog(viewer, path).exec()
