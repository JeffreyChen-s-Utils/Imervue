"""Frosted-glass dialog — random local scatter, apply and save a copy.

Pure math in :mod:`Imervue.image.frosted_glass`; this is the Qt shell (a radius
slider and a seed spin box, shared background worker).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QSpinBox,
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
from Imervue.image.frosted_glass import frosted_glass
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_RADIUS_MAX = 64
_RADIUS_DEFAULT = 4
_SEED_MAX = 9999


class FrostedGlassDialog(QDialog):
    """A radius slider + seed spin box that scatter pixels and save a copy."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("frosted_title", "Frosted Glass"))
        self.setMinimumWidth(360)

        self._radius, _, radius_row = labeled_slider(0, _RADIUS_MAX, _RADIUS_DEFAULT)
        self._seed = QSpinBox()
        self._seed.setRange(0, _SEED_MAX)

        form = QFormLayout()
        form.addRow(lang.get("frosted_radius", "Radius (px):"), radius_row)
        form.addRow(lang.get("frosted_seed", "Seed:"), self._seed)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        radius = int(self._radius.value())
        seed = int(self._seed.value())
        self._worker = EffectWorker(
            self._path,
            lambda arr: frosted_glass(arr, radius, seed),
            output_path(self._path, "frosted"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "frosted_failed", "Frosted glass failed")
        if ok:
            self.accept()


def open_frosted_glass(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        FrostedGlassDialog(viewer, path).exec()
