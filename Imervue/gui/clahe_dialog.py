"""CLAHE dialog — adaptive local-contrast equalization, applied and saved.

Pure math in :mod:`Imervue.image.clahe`; this is the Qt shell (clip-limit and
tile-count sliders, background worker).
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
from Imervue.image.clahe import apply_clahe
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.clahe_dialog")

_CLIP_SCALE = 10.0


class _ClaheWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, clip_limit: float, tiles: int, out_path: str):
        super().__init__()
        self._path = path
        self._clip = clip_limit
        self._tiles = tiles
        self._out = out_path

    def run(self) -> None:
        try:
            arr = apply_clahe(load_rgba(self._path), self._clip, self._tiles)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("CLAHE failed: %s", exc)
            self.done.emit(False, str(exc))


class ClaheDialog(QDialog):
    """Clip-limit / tile sliders that apply CLAHE to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _ClaheWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("clahe_title", "CLAHE (Local Equalize)"))
        self.setMinimumWidth(380)

        self._clip = QSlider(Qt.Orientation.Horizontal)
        self._clip.setRange(10, 60)   # 1.0 .. 6.0
        self._clip.setValue(20)
        self._tiles = QSlider(Qt.Orientation.Horizontal)
        self._tiles.setRange(2, 16)
        self._tiles.setValue(8)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("clahe_clip", "Clip limit:")))
        layout.addWidget(self._clip)
        layout.addWidget(QLabel(lang.get("clahe_tiles", "Tiles:")))
        layout.addWidget(self._tiles)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_clahe.png")
        self._worker = _ClaheWorker(
            self._path, self._clip.value() / _CLIP_SCALE, self._tiles.value(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "clahe_failed", "CLAHE failed")
        if ok:
            self.accept()


def open_clahe(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        ClaheDialog(viewer, path).exec()
