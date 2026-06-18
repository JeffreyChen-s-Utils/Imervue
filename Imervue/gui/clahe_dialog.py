"""CLAHE dialog — adaptive local-contrast equalization, applied and saved.

Pure math in :mod:`Imervue.image.clahe`; this is the Qt shell (clip-limit and
tile-count sliders, background worker) saving a copy next to the source.
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
            arr = _load_rgba(self._path)
            Image.fromarray(apply_clahe(arr, self._clip, self._tiles), mode="RGBA").save(
                self._out)
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
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_clahe.png")
        self._worker = _ClaheWorker(
            self._path, self._clip.value() / _CLIP_SCALE, self._tiles.value(), str(out_path))
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
                toast.error(f"{lang.get('clahe_failed', 'CLAHE failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_clahe(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        ClaheDialog(viewer, str(images[idx])).exec()
