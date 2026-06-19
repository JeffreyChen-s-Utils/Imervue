"""Background-flatten dialog — remove a smooth gradient and save a copy.

Pure math in :mod:`Imervue.image.flatten_field`; this is the Qt shell (degree
slider, subtract/divide toggle, background worker).
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
from Imervue.image.flatten_field import flatten_background
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.flatten_field_dialog")


class _FlattenWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, degree: int, divide: bool, out_path: str):
        super().__init__()
        self._path = path
        self._degree = degree
        self._divide = divide
        self._out = out_path

    def run(self) -> None:
        try:
            result = flatten_background(load_rgba(self._path), self._degree, divide=self._divide)
            Image.fromarray(result, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Background flatten failed: %s", exc)
            self.done.emit(False, str(exc))


class FlattenFieldDialog(QDialog):
    """Degree slider + subtract/divide toggle applied to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _FlattenWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("flatten_title", "Flatten Background"))
        self.setMinimumWidth(380)

        self._degree = QSlider(Qt.Orientation.Horizontal)
        self._degree.setRange(1, 4)
        self._degree.setValue(2)
        self._divide = QCheckBox(lang.get("flatten_divide", "Divide (vignetting)"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("flatten_degree", "Gradient degree:")))
        layout.addWidget(self._degree)
        layout.addWidget(self._divide)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_flat.png")
        self._worker = _FlattenWorker(
            self._path, self._degree.value(), self._divide.isChecked(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "flatten_failed", "Flatten failed")
        if ok:
            self.accept()


def open_flatten_field(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        FlattenFieldDialog(viewer, path).exec()
