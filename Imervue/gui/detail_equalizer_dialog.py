"""Detail equalizer dialog — per-scale contrast, apply and save a copy.

Pure math in :mod:`Imervue.image.detail_equalizer`; this is the Qt shell: one
gain slider per detail band (fine → coarse) over the shared background worker.
A gain of 1.0 is neutral.
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
from Imervue.image.detail_equalizer import apply_detail_equalizer
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_SCALE = 100.0
_GAIN_MAX = 400
_NEUTRAL = 100
# (lang key, fallback) for each detail band, finest to coarsest.
_BANDS = (
    ("detail_eq_fine", "Fine:"),
    ("detail_eq_medium", "Medium:"),
    ("detail_eq_coarse", "Coarse:"),
    ("detail_eq_broad", "Broad:"),
)


def _two_dp(value: int) -> str:
    return f"{value / _SCALE:.2f}"


class DetailEqualizerDialog(QDialog):
    """One gain slider per detail band (1.0 neutral); applies and saves a copy."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("detail_eq_title", "Detail Equalizer"))
        self.setMinimumWidth(380)

        form = QFormLayout()
        self._bands: list[QSlider] = []
        for key, fallback in _BANDS:
            slider, _, row = labeled_slider(0, _GAIN_MAX, _NEUTRAL, _two_dp)
            self._bands.append(slider)
            form.addRow(lang.get(key, fallback), row)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        gains = tuple(slider.value() / _SCALE for slider in self._bands)
        self._worker = EffectWorker(
            self._path,
            lambda arr: apply_detail_equalizer(arr, gains),
            output_path(self._path, "detaileq"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(
            self._viewer, ok, message, "detail_eq_failed", "Detail equalizer failed")
        if ok:
            self.accept()


def open_detail_equalizer(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        DetailEqualizerDialog(viewer, path).exec()
