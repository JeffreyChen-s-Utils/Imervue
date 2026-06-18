"""Document binarization dialog — Sauvola threshold, applied and saved.

Pure math in :mod:`Imervue.image.binarize`; this is the Qt shell (window-size
and k sliders, background worker) for turning a photographed/scanned page into
clean black-on-white.
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

from Imervue.image.binarize import sauvola_binarize
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.binarize_dialog")

_K_SCALE = 100.0


class _BinarizeWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, window: int, k: float, out_path: str):
        super().__init__()
        self._path = path
        self._window = window
        self._k = k
        self._out = out_path

    def run(self) -> None:
        try:
            arr = _load_rgba(self._path)
            Image.fromarray(sauvola_binarize(arr, self._window, self._k), mode="RGBA").save(
                self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Binarize failed: %s", exc)
            self.done.emit(False, str(exc))


class BinarizeDialog(QDialog):
    """Window / k sliders that binarize the current image (Sauvola)."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _BinarizeWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("binarize_title", "Document Binarize"))
        self.setMinimumWidth(380)

        self._window = QSlider(Qt.Orientation.Horizontal)
        self._window.setRange(5, 75)
        self._window.setValue(25)
        self._k = QSlider(Qt.Orientation.Horizontal)
        self._k.setRange(5, 50)   # 0.05 .. 0.50
        self._k.setValue(20)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("binarize_window", "Window size:")))
        layout.addWidget(self._window)
        layout.addWidget(QLabel(lang.get("binarize_k", "Threshold k:")))
        layout.addWidget(self._k)
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
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_bw.png")
        self._worker = _BinarizeWorker(
            self._path, self._window.value(), self._k.value() / _K_SCALE, str(out_path))
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
                toast.error(f"{lang.get('binarize_failed', 'Binarize failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_binarize(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        BinarizeDialog(viewer, str(images[idx])).exec()
