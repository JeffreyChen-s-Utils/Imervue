"""Emboss dialog — directional-light relief, apply and save a copy.

Pure math in :mod:`Imervue.image.emboss`; this is the Qt shell (azimuth /
elevation / depth sliders + a greyscale toggle, shared background worker).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
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
from Imervue.image.emboss import apply_emboss
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_DEPTH_SCALE = 10.0
_AZIMUTH_DEFAULT = 135
_ELEVATION_DEFAULT = 45
_DEPTH_DEFAULT = 10


def _one_dp(value: int) -> str:
    return f"{value / _DEPTH_SCALE:.1f}"


class EmbossDialog(QDialog):
    """Azimuth / elevation / depth sliders that emboss the image and save a copy."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("emboss_title", "Emboss"))
        self.setMinimumWidth(360)

        self._azimuth, _, azimuth_row = labeled_slider(0, 360, _AZIMUTH_DEFAULT)
        self._elevation, _, elevation_row = labeled_slider(0, 90, _ELEVATION_DEFAULT)
        self._depth, _, depth_row = labeled_slider(0, 100, _DEPTH_DEFAULT, _one_dp)
        self._grayscale = QCheckBox(lang.get("emboss_grayscale", "Greyscale relief"))
        self._grayscale.setChecked(True)

        form = QFormLayout()
        form.addRow(lang.get("emboss_azimuth", "Light azimuth (°):"), azimuth_row)
        form.addRow(lang.get("emboss_elevation", "Light elevation (°):"), elevation_row)
        form.addRow(lang.get("emboss_depth", "Depth:"), depth_row)
        form.addRow("", self._grayscale)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        azimuth = float(self._azimuth.value())
        elevation = float(self._elevation.value())
        depth = self._depth.value() / _DEPTH_SCALE
        grayscale = self._grayscale.isChecked()
        self._worker = EffectWorker(
            self._path,
            lambda arr: apply_emboss(arr, azimuth, elevation, depth, grayscale),
            output_path(self._path, "emboss"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "emboss_failed", "Emboss failed")
        if ok:
            self.accept()


def open_emboss(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        EmbossDialog(viewer, path).exec()
