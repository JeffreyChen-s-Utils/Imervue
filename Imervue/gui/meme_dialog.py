"""Meme caption dialog — top/bottom Impact text, applied and saved.

Pure drawing in :mod:`Imervue.image.meme`; this is the Qt shell (top/bottom
text fields, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
)
from Imervue.image.meme import make_meme
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.meme_dialog")


class _MemeWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, top: str, bottom: str, out_path: str):
        super().__init__()
        self._path = path
        self._top = top
        self._bottom = bottom
        self._out = out_path

    def run(self) -> None:
        try:
            arr = make_meme(load_rgba(self._path), self._top, self._bottom)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Meme failed: %s", exc)
            self.done.emit(False, str(exc))


class MemeDialog(QDialog):
    """Top/bottom caption fields applied to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _MemeWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("meme_title", "Meme Caption"))
        self.setMinimumWidth(380)

        self._top = QLineEdit()
        self._bottom = QLineEdit()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("meme_top", "Top text:")))
        layout.addWidget(self._top)
        layout.addWidget(QLabel(lang.get("meme_bottom", "Bottom text:")))
        layout.addWidget(self._bottom)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_meme.png")
        self._worker = _MemeWorker(
            self._path, self._top.text(), self._bottom.text(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "meme_failed", "Meme failed")
        if ok:
            self.accept()


def open_meme(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        MemeDialog(viewer, path).exec()
