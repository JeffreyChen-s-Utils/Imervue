"""Shared helpers for the "load current image → apply → save a copy" dialogs.

Many single-image tool dialogs (clarity/dehaze, CLAHE, flatten, dither, HSL,
frame, scale bar, ID sheet …) follow the same shape: load the current image as
RGBA, run a pure transform off the UI thread, save a sibling file and toast the
result. These helpers hold that shared boilerplate in one place so each dialog
only carries its own widgets and transform call.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from Imervue.multi_language.language_wrapper import language_wrapper

logger = logging.getLogger("Imervue.apply_save")

_LABEL_WIDTH = 40


class EffectWorker(QThread):
    """Run a pure ``RGBA -> RGBA`` transform off the UI thread and save the result.

    Each apply-and-save dialog passes a ``transform`` closure that already binds
    its slider values, so this one worker replaces the near-identical per-effect
    worker each dialog used to carry.
    """

    done = Signal(bool, str)

    def __init__(self, path: str, transform: Callable[[np.ndarray], np.ndarray], out_path: str):
        super().__init__()
        self._path = path
        self._transform = transform
        self._out = out_path

    def run(self) -> None:
        try:
            result = self._transform(load_rgba(self._path))
            Image.fromarray(result, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Effect failed: %s", exc)
            self.done.emit(False, str(exc))


def make_slider(minimum: int, maximum: int, value: int) -> QSlider:
    """Return a horizontal :class:`QSlider` over ``[minimum, maximum]`` set to *value*."""
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    return slider


def slider_row(slider: QSlider, label: QLabel) -> QWidget:
    """Pack *slider* and its live value *label* into one stretchable row widget."""
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(slider, stretch=1)
    label.setMinimumWidth(_LABEL_WIDTH)
    row.addWidget(label)
    return container


def labeled_slider(
    minimum: int, maximum: int, value: int, fmt: Callable[[int], str] = str,
) -> tuple[QSlider, QLabel, QWidget]:
    """Return a slider, a value label that tracks it via *fmt*, and their packed row."""
    slider = make_slider(minimum, maximum, value)
    label = QLabel(fmt(value))
    slider.valueChanged.connect(lambda v: label.setText(fmt(v)))
    return slider, label, slider_row(slider, label)


def output_path(source: str, suffix: str) -> str:
    """Return a sibling PNG path of *source* tagged with *suffix* (e.g. ``_emboss``)."""
    path = Path(source)
    return str(path.with_name(f"{path.stem}_{suffix}.png"))


def load_rgba(path: str) -> np.ndarray:
    """Load *path* as an HxWx4 RGBA uint8 array."""
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def current_image_path(viewer) -> str | None:
    """Return the viewer's current deep-zoom image path, or None."""
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        return str(images[idx])
    return None


def apply_save_buttons(reject: Callable[[], None], apply_: Callable[[], None]) -> QHBoxLayout:
    """Build the standard right-aligned Cancel / Apply & Save button row."""
    lang = language_wrapper.language_word_dict
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton(lang.get("export_cancel", "Cancel"))
    cancel.clicked.connect(reject)
    apply_btn = QPushButton(lang.get("local_contrast_apply", "Apply & Save"))
    apply_btn.clicked.connect(apply_)
    row.addWidget(cancel)
    row.addWidget(apply_btn)
    return row


def notify_saved(
    viewer, ok: bool, message: str, failed_key: str, failed_fallback: str,
) -> None:
    """Toast the outcome of a save: the saved filename, or a failure reason."""
    lang = language_wrapper.language_word_dict
    toast = getattr(getattr(viewer, "main_window", None), "toast", None)
    if toast is None:
        return
    if ok:
        toast.info(lang.get("local_contrast_done", "Saved {path}").format(
            path=Path(message).name))
    else:
        toast.error(f"{lang.get(failed_key, failed_fallback)}: {message}")
