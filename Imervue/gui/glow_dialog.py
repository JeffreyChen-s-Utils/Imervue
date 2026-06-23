"""Glow dialog — apply a diffuse-glow / Orton bloom and save a copy.

Pure math in :mod:`Imervue.image.glow`; this is the Qt shell (amount / radius /
threshold sliders, background worker) following the shared apply-and-save
pattern.
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
from Imervue.image.glow import apply_glow
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.glow_dialog")

_PERCENT = 100.0
_RADIUS_MIN = 1
_RADIUS_MAX = 100
_DEFAULT_AMOUNT = 50
_DEFAULT_RADIUS = 15
_DEFAULT_THRESHOLD = 0


class _GlowWorker(QThread):
    done = Signal(bool, str)

    def __init__(
        self, path: str, amount: float, radius: int, threshold: float, out_path: str,
    ):
        super().__init__()
        self._path = path
        self._amount = amount
        self._radius = radius
        self._threshold = threshold
        self._out = out_path

    def run(self) -> None:
        try:
            result = apply_glow(
                load_rgba(self._path), self._amount, self._radius, self._threshold,
            )
            Image.fromarray(result, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Glow failed: %s", exc)
            self.done.emit(False, str(exc))


class GlowDialog(QDialog):
    """Amount / radius / threshold sliders that glow the image and save a copy."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _GlowWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("glow_title", "Diffuse Glow"))
        self.setMinimumWidth(360)

        self._amount = self._percent_slider(_DEFAULT_AMOUNT)
        self._amount_label = QLabel(str(_DEFAULT_AMOUNT))
        self._amount.valueChanged.connect(lambda v: self._amount_label.setText(str(v)))
        self._radius = QSlider(Qt.Orientation.Horizontal)
        self._radius.setRange(_RADIUS_MIN, _RADIUS_MAX)
        self._radius.setValue(_DEFAULT_RADIUS)
        self._radius_label = QLabel(str(_DEFAULT_RADIUS))
        self._radius.valueChanged.connect(lambda v: self._radius_label.setText(str(v)))
        self._threshold = self._percent_slider(_DEFAULT_THRESHOLD)
        self._threshold_label = QLabel(str(_DEFAULT_THRESHOLD))
        self._threshold.valueChanged.connect(
            lambda v: self._threshold_label.setText(str(v)),
        )

        form = QFormLayout()
        form.addRow(
            lang.get("glow_amount", "Amount (%):"),
            _slider_row(self._amount, self._amount_label),
        )
        form.addRow(
            lang.get("glow_radius", "Radius (px):"),
            _slider_row(self._radius, self._radius_label),
        )
        form.addRow(
            lang.get("glow_threshold", "Highlight threshold (%):"),
            _slider_row(self._threshold, self._threshold_label),
        )
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    @staticmethod
    def _percent_slider(value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, int(_PERCENT))
        slider.setValue(value)
        return slider

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_glow.png")
        self._worker = _GlowWorker(
            self._path,
            self._amount.value() / _PERCENT,
            int(self._radius.value()),
            self._threshold.value() / _PERCENT,
            str(out_path),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "glow_failed", "Glow failed")
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


def open_glow(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        GlowDialog(viewer, path).exec()
