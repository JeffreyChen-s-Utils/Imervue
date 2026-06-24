"""Polar-coordinate dialog — wrap/unroll an image, apply and save a copy.

Pure math in :mod:`Imervue.image.polar`; this is the Qt shell (direction and
invert toggles, shared background worker).
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
    notify_saved,
    output_path,
)
from Imervue.image.polar import polar_distort
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class PolarDialog(QDialog):
    """Direction / invert toggles that warp between polar and rectangular, then save."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("polar_title", "Polar Coordinates"))
        self.setMinimumWidth(360)

        self._to_polar = QCheckBox(lang.get("polar_to_polar", "Wrap into a disc"))
        self._to_polar.setChecked(True)
        self._invert = QCheckBox(lang.get("polar_invert", "Invert radius"))

        form = QFormLayout()
        form.addRow("", self._to_polar)
        form.addRow("", self._invert)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        to_polar = self._to_polar.isChecked()
        invert = self._invert.isChecked()
        self._worker = EffectWorker(
            self._path,
            lambda arr: polar_distort(arr, to_polar, invert),
            output_path(self._path, "polar"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "polar_failed", "Polar warp failed")
        if ok:
            self.accept()


def open_polar(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        PolarDialog(viewer, path).exec()
