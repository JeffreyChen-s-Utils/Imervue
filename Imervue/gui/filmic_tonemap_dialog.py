"""Filmic tone-map dialog — highlight rolloff, apply and save a copy.

Pure math in :mod:`Imervue.image.filmic_tonemap`; this is the Qt shell (exposure
/ white-point / contrast / saturation sliders + a curve selector).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import (
    EffectWorker,
    apply_save_buttons,
    current_image_path,
    labeled_slider,
    notify_saved,
    output_path,
)
from Imervue.image.filmic_tonemap import HABLE, REINHARD, apply_filmic_tonemap
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_SCALE = 100.0
_EXPOSURE_RANGE = 600
_WHITE_DEFAULT = 400
_CONTRAST_MIN = 10
_CONTRAST_DEFAULT = 100
_SATURATION_DEFAULT = 100
_MODES = (REINHARD, HABLE)


def _two_dp(value: int) -> str:
    return f"{value / _SCALE:.2f}"


class FilmicTonemapDialog(QDialog):
    """Exposure / white / contrast / saturation sliders that tone-map and save."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("filmic_title", "Filmic Tone Map"))
        self.setMinimumWidth(360)

        self._exposure, _, exposure_row = labeled_slider(
            -_EXPOSURE_RANGE, _EXPOSURE_RANGE, 0, _two_dp)
        self._white, _, white_row = labeled_slider(10, 6400, _WHITE_DEFAULT, _two_dp)
        self._contrast, _, contrast_row = labeled_slider(
            _CONTRAST_MIN, 400, _CONTRAST_DEFAULT, _two_dp)
        self._saturation, _, saturation_row = labeled_slider(
            0, 400, _SATURATION_DEFAULT, _two_dp)
        self._mode = QComboBox()
        self._mode.addItems(_MODES)

        form = QFormLayout()
        form.addRow(lang.get("filmic_exposure", "Exposure (stops):"), exposure_row)
        form.addRow(lang.get("filmic_white", "White point:"), white_row)
        form.addRow(lang.get("filmic_contrast", "Contrast:"), contrast_row)
        form.addRow(lang.get("filmic_saturation", "Saturation:"), saturation_row)
        form.addRow(lang.get("filmic_mode", "Curve:"), self._mode)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        exposure = self._exposure.value() / _SCALE
        white = self._white.value() / _SCALE
        contrast = self._contrast.value() / _SCALE
        saturation = self._saturation.value() / _SCALE
        mode = self._mode.currentText()
        self._worker = EffectWorker(
            self._path,
            lambda arr: apply_filmic_tonemap(
                arr, exposure, white, contrast, saturation, mode),
            output_path(self._path, "filmic"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "filmic_failed", "Tone map failed")
        if ok:
            self.accept()


def open_filmic_tonemap(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        FilmicTonemapDialog(viewer, path).exec()
