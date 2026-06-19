"""Collage dialog — composite the selected images into a grid montage.

Pure compositing in :mod:`Imervue.image.collage`; this is the Qt shell (column
count, background worker) saving a ``collage.png`` next to the first image.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QSpinBox, QVBoxLayout, QWidget

from Imervue.gui._apply_save import apply_save_buttons, load_rgba, notify_saved
from Imervue.image.collage import build_collage
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.collage_dialog")


class _CollageWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, paths: list[str], columns: int, out_path: str):
        super().__init__()
        self._paths = paths
        self._columns = columns
        self._out = out_path

    def run(self) -> None:
        try:
            images = [load_rgba(p) for p in self._paths]
            Image.fromarray(build_collage(images, self._columns), mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Collage failed: %s", exc)
            self.done.emit(False, str(exc))


class CollageDialog(QDialog):
    """Pick a column count and composite the images into a grid."""

    def __init__(self, viewer: GPUImageView, paths: list[str], parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._paths = paths
        self._worker: _CollageWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("collage_title", "Collage"))
        self.setMinimumWidth(360)

        self._columns = QSpinBox()
        self._columns.setRange(1, 12)
        self._columns.setValue(min(3, max(1, len(paths))))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("collage_count", "Images: {n}").format(n=len(paths))))
        layout.addWidget(QLabel(lang.get("collage_columns", "Columns:")))
        layout.addWidget(self._columns)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None or not self._paths:
            return
        out_path = Path(self._paths[0]).with_name("collage.png")
        self._worker = _CollageWorker(self._paths, self._columns.value(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "collage_failed", "Collage failed")
        if ok:
            self.accept()


def open_collage(viewer: GPUImageView) -> None:
    paths = list(getattr(viewer, "selected_tiles", []) or [])
    if not paths:
        paths = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    if paths:
        CollageDialog(viewer, [str(p) for p in paths]).exec()
