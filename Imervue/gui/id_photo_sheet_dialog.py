"""Passport / ID photo sheet dialog.

Pure imposition in :mod:`Imervue.image.id_photo_sheet`; this is the Qt shell
(ID size + paper pickers, background worker) saving a sheet next to the source.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
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
            arr = _load_rgba(self._path)
            Image.fromarray(id_photo_sheet(arr, self._photo_mm, self._paper), mode="RGBA").save(
                self._out)
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
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_idsheet.png")
        self._worker = _SheetWorker(
            self._path, self._size_combo.currentData(),
            self._paper_combo.currentText(), str(out_path))
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
                toast.error(f"{lang.get('idsheet_failed', 'ID sheet failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_id_photo_sheet(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        IdPhotoSheetDialog(viewer, str(images[idx])).exec()
