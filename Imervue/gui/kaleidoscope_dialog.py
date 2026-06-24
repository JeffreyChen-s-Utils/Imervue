"""Kaleidoscope dialog — mirror wedges, apply and save a copy.

Pure math in :mod:`Imervue.image.kaleidoscope`; this is the Qt shell (segment
count and a rotation slider, shared background worker).
"""
from __future__ import annotations

import math
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
from Imervue.image.kaleidoscope import kaleidoscope
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_SEGMENTS_MIN = 2
_SEGMENTS_MAX = 24
_SEGMENTS_DEFAULT = 6


class KaleidoscopeDialog(QDialog):
    """Segment-count and rotation sliders that kaleidoscope the image and save."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("kaleidoscope_title", "Kaleidoscope"))
        self.setMinimumWidth(360)

        self._segments, _, segments_row = labeled_slider(
            _SEGMENTS_MIN, _SEGMENTS_MAX, _SEGMENTS_DEFAULT)
        self._angle, _, angle_row = labeled_slider(0, 360, 0)

        form = QFormLayout()
        form.addRow(lang.get("kaleidoscope_segments", "Segments:"), segments_row)
        form.addRow(lang.get("kaleidoscope_angle", "Rotation (°):"), angle_row)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        segments = int(self._segments.value())
        angle_offset = math.radians(self._angle.value())
        self._worker = EffectWorker(
            self._path,
            lambda arr: kaleidoscope(arr, segments, None, angle_offset),
            output_path(self._path, "kaleidoscope"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(
            self._viewer, ok, message, "kaleidoscope_failed", "Kaleidoscope failed")
        if ok:
            self.accept()


def open_kaleidoscope(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        KaleidoscopeDialog(viewer, path).exec()
