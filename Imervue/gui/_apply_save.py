"""Shared helpers for the "load current image → apply → save a copy" dialogs.

Many single-image tool dialogs (clarity/dehaze, CLAHE, flatten, dither, HSL,
frame, scale bar, ID sheet …) follow the same shape: load the current image as
RGBA, run a pure transform off the UI thread, save a sibling file and toast the
result. These helpers hold that shared boilerplate in one place so each dialog
only carries its own widgets and transform call.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtWidgets import QHBoxLayout, QPushButton

from Imervue.multi_language.language_wrapper import language_wrapper


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
