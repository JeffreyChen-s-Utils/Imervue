"""Otsu auto-threshold dialog — global binarization, applied and saved.

Pure math in :mod:`Imervue.image.otsu`; this is the Qt shell (an invert toggle
and a background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
)
from Imervue.image.otsu import otsu_binarize
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.otsu_dialog")


class _OtsuWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, invert: bool, out_path: str):
        super().__init__()
        self._path = path
        self._invert = invert
        self._out = out_path

    def run(self) -> None:
        try:
            arr = otsu_binarize(load_rgba(self._path), invert=self._invert)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Otsu threshold failed: %s", exc)
            self.done.emit(False, str(exc))


class OtsuDialog(QDialog):
    """Invert toggle that Otsu-thresholds the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _OtsuWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("otsu_title", "Otsu Threshold"))
        self.setMinimumWidth(340)

        self._invert = QCheckBox(lang.get("otsu_invert", "Invert"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("otsu_hint", "Global auto-threshold to black & white.")))
        layout.addWidget(self._invert)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_otsu.png")
        self._worker = _OtsuWorker(self._path, self._invert.isChecked(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "otsu_failed", "Otsu threshold failed")
        if ok:
            self.accept()


def open_otsu(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        OtsuDialog(viewer, path).exec()
