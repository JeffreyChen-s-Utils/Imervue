"""Ordered-dither dialog — quantize to N levels with a Bayer screen, and save.

Pure math in :mod:`Imervue.image.dither`; this is the Qt shell (levels slider,
background worker).
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
            arr = _load_rgba(self._path)
            Image.fromarray(ordered_dither(arr, self._levels), mode="RGBA").save(self._out)
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
        layout.addLayout(self._build_buttons(lang))

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
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_dither.png")
        self._worker = _DitherWorker(self._path, self._levels.value(), str(out_path))
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
                toast.error(f"{lang.get('dither_failed', 'Dither failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_dither(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        DitherDialog(viewer, str(images[idx])).exec()
