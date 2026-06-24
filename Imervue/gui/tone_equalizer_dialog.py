"""Tone equalizer dialog — per-zone exposure, apply and save a copy.

Pure math in :mod:`Imervue.image.tone_equalizer`; this is the Qt shell: one
exposure slider per luminance zone (shadows → highlights) plus a smoothing
slider, over the shared background worker.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog, QFormLayout, QSlider, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    EffectWorker,
    apply_save_buttons,
    current_image_path,
    labeled_slider,
    notify_saved,
    output_path,
)
from Imervue.image.tone_equalizer import apply_tone_equalizer
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_SCALE = 100.0
_GAIN_RANGE = 400
_SMOOTHING_MAX = 50
_SMOOTHING_DEFAULT = 12
# (lang key, fallback) for each zone, darkest to brightest.
_ZONES = (
    ("tone_eq_blacks", "Blacks:"),
    ("tone_eq_shadows", "Shadows:"),
    ("tone_eq_midtones", "Midtones:"),
    ("tone_eq_highlights", "Highlights:"),
    ("tone_eq_whites", "Whites:"),
)


def _two_dp(value: int) -> str:
    return f"{value / _SCALE:.2f}"


class ToneEqualizerDialog(QDialog):
    """One exposure slider per zone + a smoothing slider; applies and saves a copy."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("tone_eq_title", "Tone Equalizer"))
        self.setMinimumWidth(380)

        form = QFormLayout()
        self._zones: list[QSlider] = []
        for key, fallback in _ZONES:
            slider, _, row = labeled_slider(-_GAIN_RANGE, _GAIN_RANGE, 0, _two_dp)
            self._zones.append(slider)
            form.addRow(lang.get(key, fallback), row)
        self._smoothing, _, smoothing_row = labeled_slider(
            0, _SMOOTHING_MAX, _SMOOTHING_DEFAULT)
        form.addRow(lang.get("tone_eq_smoothing", "Smoothing:"), smoothing_row)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        gains = tuple(slider.value() / _SCALE for slider in self._zones)
        smoothing = int(self._smoothing.value())
        self._worker = EffectWorker(
            self._path,
            lambda arr: apply_tone_equalizer(arr, gains, smoothing),
            output_path(self._path, "toneeq"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "tone_eq_failed", "Tone equalizer failed")
        if ok:
            self.accept()


def open_tone_equalizer(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        ToneEqualizerDialog(viewer, path).exec()
