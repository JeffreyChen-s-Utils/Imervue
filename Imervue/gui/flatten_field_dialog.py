"""Background-flatten dialog — remove a smooth gradient and save a copy.

Pure math in :mod:`Imervue.image.flatten_field`; this is the Qt shell (degree
slider, subtract/divide toggle, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.flatten_field import flatten_background
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.flatten_field_dialog")


class _FlattenWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, degree: int, divide: bool, out_path: str):
        super().__init__()
        self._path = path
        self._degree = degree
        self._divide = divide
        self._out = out_path

    def run(self) -> None:
        try:
            arr = _load_rgba(self._path)
            result = flatten_background(arr, self._degree, divide=self._divide)
            Image.fromarray(result, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Background flatten failed: %s", exc)
            self.done.emit(False, str(exc))


class FlattenFieldDialog(QDialog):
    """Degree slider + subtract/divide toggle applied to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _FlattenWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("flatten_title", "Flatten Background"))
        self.setMinimumWidth(380)

        self._degree = QSlider(Qt.Orientation.Horizontal)
        self._degree.setRange(1, 4)
        self._degree.setValue(2)
        self._divide = QCheckBox(lang.get("flatten_divide", "Divide (vignetting)"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("flatten_degree", "Gradient degree:")))
        layout.addWidget(self._degree)
        layout.addWidget(self._divide)
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
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_flat.png")
        self._worker = _FlattenWorker(
            self._path, self._degree.value(), self._divide.isChecked(), str(out_path))
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
                toast.error(f"{lang.get('flatten_failed', 'Flatten failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_flatten_field(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        FlattenFieldDialog(viewer, str(images[idx])).exec()
