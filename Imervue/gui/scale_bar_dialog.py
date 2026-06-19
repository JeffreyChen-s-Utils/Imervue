"""Scale-bar dialog — calibrate pixels-per-unit and burn in a scale bar.

Pure drawing in :mod:`Imervue.image.scale_bar`; this is the Qt shell
(pixels-per-unit + unit-label inputs, background worker) saving a copy.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.scale_bar import add_scale_bar
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.scale_bar_dialog")

_PPU_MAX = 100000.0


class _ScaleBarWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, px_per_unit: float, unit: str, out_path: str):
        super().__init__()
        self._path = path
        self._ppu = px_per_unit
        self._unit = unit
        self._out = out_path

    def run(self) -> None:
        try:
            arr = _load_rgba(self._path)
            Image.fromarray(add_scale_bar(arr, self._ppu, self._unit), mode="RGBA").save(
                self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Scale bar failed: %s", exc)
            self.done.emit(False, str(exc))


class ScaleBarDialog(QDialog):
    """Pixels-per-unit + unit label, drawn onto the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _ScaleBarWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("scalebar_title", "Scale Bar"))
        self.setMinimumWidth(360)

        self._ppu = QDoubleSpinBox()
        self._ppu.setRange(0.001, _PPU_MAX)
        self._ppu.setValue(10.0)
        self._ppu.setDecimals(3)
        self._unit = QLineEdit("um")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("scalebar_ppu", "Pixels per unit:")))
        layout.addWidget(self._ppu)
        layout.addWidget(QLabel(lang.get("scalebar_unit", "Unit label:")))
        layout.addWidget(self._unit)
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
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_scalebar.png")
        unit = self._unit.text().strip() or "px"
        self._worker = _ScaleBarWorker(self._path, self._ppu.value(), unit, str(out_path))
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
                toast.error(f"{lang.get('scalebar_failed', 'Scale bar failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_scale_bar(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        ScaleBarDialog(viewer, str(images[idx])).exec()
