"""Scale-bar dialog — calibrate pixels-per-unit and burn in a scale bar.

Pure drawing in :mod:`Imervue.image.scale_bar`; this is the Qt shell
(pixels-per-unit + unit-label inputs, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
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
            arr = add_scale_bar(load_rgba(self._path), self._ppu, self._unit)
            Image.fromarray(arr, mode="RGBA").save(self._out)
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
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

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
        notify_saved(self._viewer, ok, message, "scalebar_failed", "Scale bar failed")
        if ok:
            self.accept()


def open_scale_bar(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        ScaleBarDialog(viewer, path).exec()
