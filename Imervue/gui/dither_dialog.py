"""Ordered-dither dialog — quantize to N levels with a Bayer screen, and save.

Pure math in :mod:`Imervue.image.dither`; this is the Qt shell (levels slider,
background worker).
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
from Imervue.image.dither import ordered_dither
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.dither_dialog")


class _DitherWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, levels: int, out_path: str):
        super().__init__()
        self._path = path
        self._levels = levels
        self._out = out_path

    def run(self) -> None:
        try:
            Image.fromarray(ordered_dither(load_rgba(self._path), self._levels),
                            mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Dither failed: %s", exc)
            self.done.emit(False, str(exc))


class DitherDialog(QDialog):
    """Levels slider that ordered-dithers the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _DitherWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("dither_title", "Ordered Dither"))
        self.setMinimumWidth(360)

        self._levels = QSlider(Qt.Orientation.Horizontal)
        self._levels.setRange(2, 8)
        self._levels.setValue(2)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("dither_levels", "Levels per channel:")))
        layout.addWidget(self._levels)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_dither.png")
        self._worker = _DitherWorker(self._path, self._levels.value(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "dither_failed", "Dither failed")
        if ok:
            self.accept()


def open_dither(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        DitherDialog(viewer, path).exec()
