"""Velvia dialog — luminance-weighted saturation boost, apply and save a copy.

Pure math in :mod:`Imervue.image.velvia`; this is the Qt shell (strength /
shadow-protection sliders, shared background worker).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog, QFormLayout, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    EffectWorker,
    apply_save_buttons,
    current_image_path,
    labeled_slider,
    notify_saved,
    output_path,
)
from Imervue.image.velvia import apply_velvia
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_SCALE = 100.0
_STRENGTH_MAX = 400
_STRENGTH_DEFAULT = 100
_PROTECTION_DEFAULT = 50


def _two_dp(value: int) -> str:
    return f"{value / _SCALE:.2f}"


class VelviaDialog(QDialog):
    """Strength / shadow-protection sliders that boost saturation and save a copy."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("velvia_title", "Velvia"))
        self.setMinimumWidth(360)

        self._strength, _, strength_row = labeled_slider(
            0, _STRENGTH_MAX, _STRENGTH_DEFAULT, _two_dp)
        self._protection, _, protection_row = labeled_slider(
            0, 100, _PROTECTION_DEFAULT, _two_dp)
        form = QFormLayout()
        form.addRow(lang.get("velvia_strength", "Strength:"), strength_row)
        form.addRow(lang.get("velvia_protection", "Shadow protection:"), protection_row)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        strength = self._strength.value() / _SCALE
        protection = self._protection.value() / _SCALE
        self._worker = EffectWorker(
            self._path,
            lambda arr: apply_velvia(arr, strength, protection),
            output_path(self._path, "velvia"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "velvia_failed", "Velvia failed")
        if ok:
            self.accept()


def open_velvia(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        VelviaDialog(viewer, path).exec()
