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
from Imervue.system.free_names import free_names

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
        except Exception as exc:  # a worker must always report
            # The transform can raise anything: ImportError for an optional
            # backend (opencv isn't a default dependency), cv2.error, MemoryError,
            # or PIL's DecompressionBombError. Narrowing the except let those
            # escape, so ``done`` never fired and the calling dialog hung with its
            # Apply button disabled forever. Always report the failure instead.
            logger.exception("Effect failed: %s", exc)
            self.done.emit(False, str(exc))


def finalize_worker(dialog) -> None:
    """Wait for ``dialog._worker``'s thread to stop, then drop the reference.

    Call this instead of ``self._worker = None`` in a worker's ``done`` slot.
    These dialogs are usually temporaries (``Dialog(...).exec()``), so dropping
    the last reference the moment ``done`` fires — while the OS thread is still
    returning from ``run()`` — lets the QThread be garbage-collected mid-flight,
    which Qt aborts with "QThread: Destroyed while thread is still running". The
    custom ``done`` signal is emitted as the worker's final act, so ``wait()``
    returns near-instantly; it just guarantees the thread has truly exited
    before the reference is released. Mirrors the existing auto-straighten / OCR
    dialogs, which already wait before nulling.
    """
    worker = getattr(dialog, "_worker", None)
    if worker is not None:
        worker.wait()
    dialog._worker = None


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


def output_paths(source: str, suffixes: list[str], ext: str = ".png") -> list[str]:
    """Sibling paths of *source* tagged with each of *suffixes*, none of which exists yet.

    ``photo_clahe.png``; if that is taken, ``photo_clahe_1.png`` and on — a
    second run of a tool used to save over the first one's result, and over
    any retouching done to it since. A group (frequency separation's low and
    high layers) shares one number so the pair stays recognisable. Names are
    compared the way the file system does.
    """
    path = Path(source)
    stems = [f"{path.stem}_{suffix}" for suffix in suffixes]
    return [str(name) for name in free_names(path.parent, stems, ext)]


def output_path(source: str, suffix: str, ext: str = ".png") -> str:
    """A free sibling path of *source* tagged with *suffix*: ``photo_emboss.png``, then ``_1``."""
    return output_paths(source, [suffix], ext)[0]


def load_rgba(path: str) -> np.ndarray:
    """Load *path* as an HxWx4 RGBA uint8 array, closing the file before returning.

    The pixels are as the viewer shows them: camera RAW developed at full size,
    converted from an embedded colour profile to sRGB and turned upright by
    the EXIF orientation. The tools save
    their result without EXIF or ICC, so anything else would be saved wrong for
    good. Plugins in Imervue_Plugins import this (``architecture.md`` §6).
    """
    from Imervue.gpu_image_view.images.image_loader import decode_image_file
    return decode_image_file(path)   # RAW developed at full size, SVG rasterised


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
