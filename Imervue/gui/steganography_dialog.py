"""Steganography dialog — hide a message in the image, or reveal one.

Pure encode/decode in :mod:`Imervue.image.steganography`; this dialog hides
text (saving a lossless PNG so the LSBs survive) and reveals text from the
current image.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import current_image_path, load_rgba, notify_saved
from Imervue.image.steganography import capacity_bytes, hide_message, reveal_message
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.steganography_dialog")


class _HideWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, message: str, out_path: str):
        super().__init__()
        self._path = path
        self._message = message
        self._out = out_path

    def run(self) -> None:
        try:
            arr = hide_message(load_rgba(self._path), self._message)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Hide message failed: %s", exc)
            self.done.emit(False, str(exc))


class SteganographyDialog(QDialog):
    """Hide a message into / reveal a message from the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _HideWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("stego_title", "Steganography"))
        self.setMinimumWidth(420)

        self._message = QPlainTextEdit()
        capacity = capacity_bytes(load_rgba(path))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("stego_capacity", "Message (max {n} bytes):").format(n=capacity)))
        layout.addWidget(self._message)
        layout.addLayout(self._build_buttons(lang))

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        reveal = QPushButton(lang.get("stego_reveal", "Reveal"))
        reveal.clicked.connect(self._reveal)
        hide = QPushButton(lang.get("stego_hide", "Hide & Save"))
        hide.clicked.connect(self._hide)
        close = QPushButton(lang.get("export_cancel", "Close"))
        close.clicked.connect(self.reject)
        row.addWidget(reveal)
        row.addStretch(1)
        row.addWidget(hide)
        row.addWidget(close)
        return row

    def _reveal(self) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        try:
            text = reveal_message(load_rgba(self._path))
        except (OSError, ValueError):
            text = ""
        self._message.setPlainText(text)
        toast = getattr(getattr(self._viewer, "main_window", None), "toast", None)
        if toast is not None and not text:
            toast.info(lang.get("stego_none", "No hidden message found"))

    def _hide(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_stego.png")
        self._worker = _HideWorker(self._path, self._message.toPlainText(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "stego_failed", "Hide message failed")
        if ok:
            self.accept()


def open_steganography(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        SteganographyDialog(viewer, path).exec()
