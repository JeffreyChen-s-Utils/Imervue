"""Graduated-density dialog — linear ND gradient, apply and save a copy.

Pure math in :mod:`Imervue.image.graduated_density`; this is the Qt shell
(angle / density / hardness / offset sliders, an optional tint, shared background worker).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox, QDialog, QFormLayout, QVBoxLayout, QWidget

from Imervue.gui.color_swatch import ColorSwatchButton, Rgb
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.gui._apply_save import (
    finalize_worker,
    EffectWorker,
    apply_save_buttons,
    current_image_path,
    labeled_slider,
    notify_saved,
    output_path,
)
from Imervue.image.graduated_density import apply_graduated_density
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_SCALE = 100.0
_ANGLE_DEFAULT = 0
_DENSITY_RANGE = 800
_DENSITY_DEFAULT = 100
_HARDNESS_DEFAULT = 50
_OFFSET_RANGE = 100
# (0.8, 0.9, 1.0) as 8-bit: cools the darkened side, the filter's own example.
_TINT_DEFAULT: Rgb = (204, 230, 255)
_BYTE = 255.0


def tint_multiplier(enabled: bool, rgb: Rgb) -> tuple[float, float, float] | None:
    """The per-channel multiplier ``apply_graduated_density`` takes, or None for no tint."""
    if not enabled:
        return None
    return (rgb[0] / _BYTE, rgb[1] / _BYTE, rgb[2] / _BYTE)


def _two_dp(value: int) -> str:
    return f"{value / _SCALE:.2f}"


class GraduatedDensityDialog(WorkerHostMixin, QDialog):
    """Angle / density / hardness / offset sliders that grade the frame and save."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("graduated_density_title", "Graduated Density"))
        self.setMinimumWidth(360)

        self._angle, _, angle_row = labeled_slider(0, 360, _ANGLE_DEFAULT)
        self._density, _, density_row = labeled_slider(
            -_DENSITY_RANGE, _DENSITY_RANGE, _DENSITY_DEFAULT, _two_dp)
        self._hardness, _, hardness_row = labeled_slider(0, 100, _HARDNESS_DEFAULT, _two_dp)
        self._offset, _, offset_row = labeled_slider(
            -_OFFSET_RANGE, _OFFSET_RANGE, 0, _two_dp)

        form = QFormLayout()
        form.addRow(lang.get("graduated_density_angle", "Angle (°):"), angle_row)
        form.addRow(lang.get("graduated_density_stops", "Density (stops):"), density_row)
        form.addRow(lang.get("graduated_density_hardness", "Hardness:"), hardness_row)
        form.addRow(lang.get("graduated_density_offset", "Offset:"), offset_row)
        self._tint_check = QCheckBox(lang.get("graduated_density_tint", "Tint the graded side"))
        self._tint_color = ColorSwatchButton(
            _TINT_DEFAULT, title=lang.get("graduated_density_tint", "Tint the graded side"))
        self._tint_color.setEnabled(False)
        self._tint_check.toggled.connect(self._tint_color.setEnabled)
        form.addRow(self._tint_check, self._tint_color)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        angle = float(self._angle.value())
        density = self._density.value() / _SCALE
        hardness = self._hardness.value() / _SCALE
        offset = self._offset.value() / _SCALE
        tint = tint_multiplier(self._tint_check.isChecked(), self._tint_color.rgb())
        self._worker = EffectWorker(
            self._path,
            lambda arr: apply_graduated_density(arr, angle, density, hardness, offset, tint),
            output_path(self._path, "gradnd"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        finalize_worker(self)
        notify_saved(
            self._viewer, ok, message,
            "graduated_density_failed", "Graduated density failed")
        if ok:
            self.accept()


def open_graduated_density(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        GraduatedDensityDialog(viewer, path).exec()
