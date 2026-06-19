"""Tiny Planet dialog — export a 360° panorama as a little-planet still.

Pure reprojection lives in :mod:`Imervue.image.equirectangular`; this is the Qt
shell (output-size slider, background worker). Works best on 2:1 equirectangular
panoramas; a hint warns otherwise.
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
from Imervue.image.equirectangular import DEFAULT_SIZE, tiny_planet
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.tiny_planet_dialog")

_SIZE_MIN = 512
_SIZE_MAX = 2048


class _TinyPlanetWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, size: int, out_path: str):
        super().__init__()
        self._path = path
        self._size = size
        self._out = out_path

    def run(self) -> None:
        try:
            arr = tiny_planet(load_rgba(self._path), self._size)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Tiny planet failed: %s", exc)
            self.done.emit(False, str(exc))


class TinyPlanetDialog(QDialog):
    """Pick an output size and render the current panorama as a little planet."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _TinyPlanetWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("tiny_planet_title", "Tiny Planet (360°)"))
        self.setMinimumWidth(380)

        self._size = QSlider(Qt.Orientation.Horizontal)
        self._size.setRange(_SIZE_MIN, _SIZE_MAX)
        self._size.setValue(DEFAULT_SIZE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self._hint(lang)))
        layout.addWidget(QLabel(lang.get("tiny_planet_size", "Output size (px):")))
        layout.addWidget(self._size)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _hint(self, lang: dict) -> str:
        if _safe_is_equirect(self._path):
            return lang.get("tiny_planet_size", "Output size (px):")
        return lang.get("tiny_planet_not_360",
                        "This image is not a 2:1 panorama; result may look odd.")

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_planet.png")
        self._worker = _TinyPlanetWorker(self._path, self._size.value(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "tiny_planet_failed", "Tiny planet failed")
        if ok:
            self.accept()


def _safe_is_equirect(path: str) -> bool:
    try:
        with Image.open(path) as img:
            w, h = img.size
        return h > 0 and abs(w / (2.0 * h) - 1.0) <= 0.05
    except (OSError, ValueError):
        return False


def open_tiny_planet(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        TinyPlanetDialog(viewer, path).exec()
