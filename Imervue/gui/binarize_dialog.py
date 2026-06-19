"""Document binarization dialog — Sauvola threshold, applied and saved.

Pure math in :mod:`Imervue.image.binarize`; this is the Qt shell (window-size
and k sliders, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QSlider, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
)
from Imervue.image.binarize import sauvola_binarize
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.binarize_dialog")

_K_SCALE = 100.0


class _BinarizeWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, window: int, k: float, out_path: str):
        super().__init__()
        self._path = path
        self._window = window
        self._k = k
        self._out = out_path

    def run(self) -> None:
        try:
            arr = sauvola_binarize(load_rgba(self._path), self._window, self._k)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Binarize failed: %s", exc)
            self.done.emit(False, str(exc))


class BinarizeDialog(QDialog):
    """Window / k sliders that binarize the current image (Sauvola)."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _BinarizeWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("binarize_title", "Document Binarize"))
        self.setMinimumWidth(380)

        self._window = QSlider(Qt.Orientation.Horizontal)
        self._window.setRange(5, 75)
        self._window.setValue(25)
        self._k = QSlider(Qt.Orientation.Horizontal)
        self._k.setRange(5, 50)   # 0.05 .. 0.50
        self._k.setValue(20)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("binarize_window", "Window size:")))
        layout.addWidget(self._window)
        layout.addWidget(QLabel(lang.get("binarize_k", "Threshold k:")))
        layout.addWidget(self._k)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_bw.png")
        self._worker = _BinarizeWorker(
            self._path, self._window.value(), self._k.value() / _K_SCALE, str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "binarize_failed", "Binarize failed")
        if ok:
            self.accept()


def open_binarize(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        BinarizeDialog(viewer, path).exec()
