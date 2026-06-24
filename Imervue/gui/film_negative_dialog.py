"""Film-negative dialog — invert a scanned negative, apply and save a copy.

Pure math in :mod:`Imervue.image.film_negative` (the film base is auto-estimated
from the scan); this is the Qt shell (a single output-gamma slider).
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
from Imervue.image.film_negative import apply_film_negative
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_GAMMA_SCALE = 100.0
_GAMMA_MIN = 10
_GAMMA_MAX = 600
_GAMMA_DEFAULT = 100


def _two_dp(value: int) -> str:
    return f"{value / _GAMMA_SCALE:.2f}"


class FilmNegativeDialog(QDialog):
    """A gamma slider that inverts the negative scan and saves the positive."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("film_negative_title", "Film Negative"))
        self.setMinimumWidth(360)

        self._gamma, _, gamma_row = labeled_slider(
            _GAMMA_MIN, _GAMMA_MAX, _GAMMA_DEFAULT, _two_dp)
        form = QFormLayout()
        form.addRow(lang.get("film_negative_gamma", "Gamma:"), gamma_row)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        gamma = self._gamma.value() / _GAMMA_SCALE
        self._worker = EffectWorker(
            self._path,
            lambda arr: apply_film_negative(arr, None, gamma),
            output_path(self._path, "positive"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(
            self._viewer, ok, message, "film_negative_failed", "Film negative failed")
        if ok:
            self.accept()


def open_film_negative(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        FilmNegativeDialog(viewer, path).exec()
