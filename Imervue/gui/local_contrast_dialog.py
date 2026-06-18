"""Clarity / Dehaze dialog — local-contrast and haze-removal sliders.

Groups the three local-contrast develop sliders that competitors keep
together in one panel (Lightroom Basic): Dehaze, Clarity, Texture. The pure
image math lives in :mod:`Imervue.image.dehaze` and
:mod:`Imervue.image.local_contrast`; this is the Qt shell plus a background
worker that applies them in order and saves a copy.
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

from Imervue.image.dehaze import dehaze
from Imervue.image.local_contrast import apply_clarity, apply_texture
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.local_contrast_dialog")

_SLIDER_RANGE = 100


class _LocalContrastWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, dehaze_amt: float, clarity_amt: float,
                 texture_amt: float, out_path: str):
        super().__init__()
        self._path = path
        self._dehaze = dehaze_amt
        self._clarity = clarity_amt
        self._texture = texture_amt
        self._out = out_path

    def run(self) -> None:
        try:
            arr = _load_rgba(self._path)
            if self._dehaze > 0.0:
                arr = dehaze(arr, self._dehaze)
            if self._clarity != 0.0:
                arr = apply_clarity(arr, self._clarity)
            if self._texture != 0.0:
                arr = apply_texture(arr, self._texture)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Local contrast failed: %s", exc)
            self.done.emit(False, str(exc))


class LocalContrastDialog(QDialog):
    """Dehaze / Clarity / Texture sliders applied to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _LocalContrastWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("local_contrast_title", "Clarity / Dehaze"))
        self.setMinimumWidth(380)

        self._dehaze = self._make_slider(0, _SLIDER_RANGE, 0)
        self._clarity = self._make_slider(-_SLIDER_RANGE, _SLIDER_RANGE, 0)
        self._texture = self._make_slider(-_SLIDER_RANGE, _SLIDER_RANGE, 0)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("local_contrast_dehaze", "Dehaze:")))
        layout.addWidget(self._dehaze)
        layout.addWidget(QLabel(lang.get("local_contrast_clarity", "Clarity:")))
        layout.addWidget(self._clarity)
        layout.addWidget(QLabel(lang.get("local_contrast_texture", "Texture:")))
        layout.addWidget(self._texture)
        layout.addLayout(self._build_buttons(lang))

    @staticmethod
    def _make_slider(low: int, high: int, value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setValue(value)
        return slider

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
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_local.png")
        self._worker = _LocalContrastWorker(
            self._path,
            self._dehaze.value() / _SLIDER_RANGE,
            self._clarity.value() / _SLIDER_RANGE,
            self._texture.value() / _SLIDER_RANGE,
            str(out_path),
        )
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
                toast.error(
                    f"{lang.get('local_contrast_failed', 'Adjustment failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_local_contrast(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        LocalContrastDialog(viewer, str(images[idx])).exec()
