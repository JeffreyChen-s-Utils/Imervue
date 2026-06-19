"""Passport / ID photo sheet dialog.

Pure imposition in :mod:`Imervue.image.id_photo_sheet`; this is the Qt shell
(ID size + paper pickers, background worker).
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
from Imervue.image.id_photo_sheet import PAPER_SIZES_IN, id_photo_sheet
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.id_photo_sheet_dialog")

# (label, (width_mm, height_mm))
_ID_SIZES = (
    ("35 x 45 mm", (35.0, 45.0)),
    ("2 x 2 in (US)", (50.8, 50.8)),
    ("33 x 48 mm (CN)", (33.0, 48.0)),
    ("50 x 70 mm", (50.0, 70.0)),
)


class _SheetWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, photo_mm: tuple[float, float], paper: str, out_path: str):
        super().__init__()
        self._path = path
        self._photo_mm = photo_mm
        self._paper = paper
        self._out = out_path

    def run(self) -> None:
        try:
            arr = id_photo_sheet(load_rgba(self._path), self._photo_mm, self._paper)
            Image.fromarray(arr, mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("ID sheet failed: %s", exc)
            self.done.emit(False, str(exc))


class IdPhotoSheetDialog(QDialog):
    """ID size + paper pickers that tile the current photo into a print sheet."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _SheetWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("idsheet_title", "ID Photo Sheet"))
        self.setMinimumWidth(360)

        self._size_combo = QComboBox()
        for label, mm in _ID_SIZES:
            self._size_combo.addItem(label, mm)
        self._paper_combo = QComboBox()
        self._paper_combo.addItems(list(PAPER_SIZES_IN))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("idsheet_size", "Photo size:")))
        layout.addWidget(self._size_combo)
        layout.addWidget(QLabel(lang.get("idsheet_paper", "Paper:")))
        layout.addWidget(self._paper_combo)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_idsheet.png")
        self._worker = _SheetWorker(
            self._path, self._size_combo.currentData(),
            self._paper_combo.currentText(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "idsheet_failed", "ID sheet failed")
        if ok:
            self.accept()


def open_id_photo_sheet(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        IdPhotoSheetDialog(viewer, path).exec()
