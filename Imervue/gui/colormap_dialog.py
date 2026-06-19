"""Colour-map dialog — re-colour luminance through a perceptual gradient.

Pure math in :mod:`Imervue.image.colormap`; this is the Qt shell (colour-map
picker, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
)
from Imervue.image.colormap import COLORMAPS, apply_colormap
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.colormap_dialog")


class _ColormapWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, name: str, out_path: str):
        super().__init__()
        self._path = path
        self._name = name
        self._out = out_path

    def run(self) -> None:
        try:
            arr = apply_colormap(load_rgba(self._path), self._name)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Colormap failed: %s", exc)
            self.done.emit(False, str(exc))


class ColormapDialog(QDialog):
    """Colour-map picker that re-colours the current image's luminance."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _ColormapWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("colormap_title", "Color Map"))
        self.setMinimumWidth(340)

        self._combo = QComboBox()
        for name in COLORMAPS:
            self._combo.addItem(name.title(), name)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("colormap_label", "Color map:")))
        layout.addWidget(self._combo)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_colormap.png")
        self._worker = _ColormapWorker(self._path, self._combo.currentData(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "colormap_failed", "Colormap failed")
        if ok:
            self.accept()


def open_colormap(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        ColormapDialog(viewer, path).exec()
