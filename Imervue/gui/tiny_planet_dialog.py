"""Tiny Planet dialog — export a 360° panorama as a little-planet still.

Pure reprojection lives in :mod:`Imervue.image.equirectangular`; this is the Qt
shell (output-size slider, background worker) that saves the result next to the
source. Works best on 2:1 equirectangular panoramas; a hint warns otherwise.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
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
            arr = _load_rgba(self._path)
            Image.fromarray(tiny_planet(arr, self._size), mode="RGBA").save(self._out)
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
        layout.addLayout(self._build_buttons(lang))

    def _hint(self, lang: dict) -> str:
        if _safe_is_equirect(self._path):
            return lang.get("tiny_planet_size", "Output size (px):")
        return lang.get("tiny_planet_not_360",
                        "This image is not a 2:1 panorama; result may look odd.")

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        apply_btn = QPushButton(lang.get("local_contrast_apply", "Apply & Save"))
        apply_btn.clicked.connect(self._commit)
        row.addWidget(cancel)
        row.addWidget(apply_btn)
        return row

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_planet.png")
        self._worker = _TinyPlanetWorker(self._path, self._size.value(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        lang = language_wrapper.language_word_dict
        toast = getattr(getattr(self._viewer, "main_window", None), "toast", None)
        if toast is not None:
            if ok:
                toast.info(lang.get("local_contrast_done", "Saved {path}").format(
                    path=Path(message).name))
            else:
                toast.error(
                    f"{lang.get('tiny_planet_failed', 'Tiny planet failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def _safe_is_equirect(path: str) -> bool:
    try:
        with Image.open(path) as img:
            w, h = img.size
        return h > 0 and abs(w / (2.0 * h) - 1.0) <= 0.05
    except (OSError, ValueError):
        return False


def open_tiny_planet(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        TinyPlanetDialog(viewer, str(images[idx])).exec()
