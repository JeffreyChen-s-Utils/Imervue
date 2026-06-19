"""Anaglyph 3D dialog — combine the current image (left) with a chosen right view.

Pure math in :mod:`Imervue.image.anaglyph`; this is the Qt shell (method picker
+ right-view file chooser, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
)
from Imervue.image.anaglyph import METHODS, anaglyph
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.anaglyph_dialog")


class _AnaglyphWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, left_path: str, right_path: str, method: str, out_path: str):
        super().__init__()
        self._left = left_path
        self._right = right_path
        self._method = method
        self._out = out_path

    def run(self) -> None:
        try:
            arr = anaglyph(load_rgba(self._left), load_rgba(self._right), self._method)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Anaglyph failed: %s", exc)
            self.done.emit(False, str(exc))


class AnaglyphDialog(QDialog):
    """Method picker + right-view chooser; the current image is the left view."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _AnaglyphWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("anaglyph_title", "Anaglyph 3D"))
        self.setMinimumWidth(420)

        self._method = QComboBox()
        for method in METHODS:
            self._method.addItem(method.title(), method)
        self._right_edit = QLineEdit()
        browse = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        browse.clicked.connect(self._choose_right)

        right_row = QHBoxLayout()
        right_row.addWidget(self._right_edit, 1)
        right_row.addWidget(browse)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("anaglyph_method", "Method:")))
        layout.addWidget(self._method)
        layout.addWidget(QLabel(lang.get("anaglyph_right", "Right-eye image:")))
        layout.addLayout(right_row)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _choose_right(self) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        chosen, _ = QFileDialog.getOpenFileName(
            self, lang.get("anaglyph_right", "Right-eye image:"), "",
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp)")
        if chosen:
            self._right_edit.setText(chosen)

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        right = self._right_edit.text().strip()
        if self._worker is not None or not right:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_anaglyph.png")
        self._worker = _AnaglyphWorker(
            self._path, right, self._method.currentData(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "anaglyph_failed", "Anaglyph failed")
        if ok:
            self.accept()


def open_anaglyph(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        AnaglyphDialog(viewer, path).exec()
