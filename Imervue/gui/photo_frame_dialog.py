"""Photo frame / caption dialog.

Pure drawing in :mod:`Imervue.image.photo_frame`; this is the Qt shell (border
and Polaroid-bottom sliders, caption field, background worker).
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
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.photo_frame import FrameOptions, add_frame
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.photo_frame_dialog")


class _FrameWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, options: FrameOptions, out_path: str):
        super().__init__()
        self._path = path
        self._options = options
        self._out = out_path

    def run(self) -> None:
        try:
            arr = _load_rgba(self._path)
            Image.fromarray(add_frame(arr, self._options), mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Frame failed: %s", exc)
            self.done.emit(False, str(exc))


class PhotoFrameDialog(QDialog):
    """Border / Polaroid-bottom / caption applied to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _FrameWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("frame_title", "Frame & Caption"))
        self.setMinimumWidth(380)

        self._border = self._make_slider(0, 200, 40)
        self._bottom = self._make_slider(0, 300, 0)
        self._caption = QLineEdit()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("frame_border", "Border (px):")))
        layout.addWidget(self._border)
        layout.addWidget(QLabel(lang.get("frame_bottom", "Polaroid bottom (px):")))
        layout.addWidget(self._bottom)
        layout.addWidget(QLabel(lang.get("frame_caption", "Caption:")))
        layout.addWidget(self._caption)
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
        options = FrameOptions(
            border=self._border.value(),
            bottom_extra=self._bottom.value(),
            caption=self._caption.text(),
        )
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_framed.png")
        self._worker = _FrameWorker(self._path, options, str(out_path))
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
                toast.error(f"{lang.get('frame_failed', 'Frame failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_photo_frame(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        PhotoFrameDialog(viewer, str(images[idx])).exec()
