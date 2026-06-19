"""Pixel-sort glitch dialog — applied and saved.

Pure math in :mod:`Imervue.image.pixel_sort`; this is the Qt shell (brightness
band sliders + orientation toggle, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QSlider, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
)
from Imervue.image.pixel_sort import pixel_sort
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.pixel_sort_dialog")


class _PixelSortWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, lower: int, upper: int, vertical: bool, out_path: str):
        super().__init__()
        self._path = path
        self._lower = lower
        self._upper = upper
        self._vertical = vertical
        self._out = out_path

    def run(self) -> None:
        try:
            arr = pixel_sort(load_rgba(self._path), self._lower, self._upper,
                             vertical=self._vertical)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Pixel sort failed: %s", exc)
            self.done.emit(False, str(exc))


class PixelSortDialog(QDialog):
    """Brightness-band sliders + orientation applied to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _PixelSortWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("pixelsort_title", "Pixel Sort"))
        self.setMinimumWidth(360)

        self._lower = self._make_slider(60)
        self._upper = self._make_slider(200)
        self._vertical = QCheckBox(lang.get("pixelsort_vertical", "Vertical"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("pixelsort_lower", "Lower threshold:")))
        layout.addWidget(self._lower)
        layout.addWidget(QLabel(lang.get("pixelsort_upper", "Upper threshold:")))
        layout.addWidget(self._upper)
        layout.addWidget(self._vertical)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    @staticmethod
    def _make_slider(value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 255)
        slider.setValue(value)
        return slider

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_pixelsort.png")
        self._worker = _PixelSortWorker(
            self._path, self._lower.value(), self._upper.value(),
            self._vertical.isChecked(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "pixelsort_failed", "Pixel sort failed")
        if ok:
            self.accept()


def open_pixel_sort(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        PixelSortDialog(viewer, path).exec()
