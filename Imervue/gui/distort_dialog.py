"""Distortion dialog — swirl / pinch / ripple, applied and saved.

Pure math in :mod:`Imervue.image.distort`; this is the Qt shell (mode picker +
strength slider, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QSlider, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
)
from Imervue.image.distort import MODES, distort
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.distort_dialog")

_STRENGTH_RANGE = 100


class _DistortWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, mode: str, strength: float, out_path: str):
        super().__init__()
        self._path = path
        self._mode = mode
        self._strength = strength
        self._out = out_path

    def run(self) -> None:
        try:
            arr = distort(load_rgba(self._path), self._mode, self._strength)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Distort failed: %s", exc)
            self.done.emit(False, str(exc))


class DistortDialog(QDialog):
    """Mode + strength applied to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _DistortWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("distort_title", "Distort"))
        self.setMinimumWidth(360)

        self._mode = QComboBox()
        for mode in MODES:
            self._mode.addItem(lang.get(f"distort_{mode}", mode.title()), mode)
        self._strength = QSlider(Qt.Orientation.Horizontal)
        self._strength.setRange(-_STRENGTH_RANGE, _STRENGTH_RANGE)
        self._strength.setValue(50)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("distort_mode", "Mode:")))
        layout.addWidget(self._mode)
        layout.addWidget(QLabel(lang.get("distort_strength", "Strength:")))
        layout.addWidget(self._strength)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_distort.png")
        self._worker = _DistortWorker(
            self._path, self._mode.currentData(),
            self._strength.value() / _STRENGTH_RANGE, str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "distort_failed", "Distort failed")
        if ok:
            self.accept()


def open_distort(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        DistortDialog(viewer, path).exec()
