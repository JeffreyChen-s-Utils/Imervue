"""Target-file-size dialog — encode the current image under a KB budget.

Pure encoding in :mod:`Imervue.image.optimize`; this is the Qt shell (format
picker + KB budget, background worker that writes the optimized file).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import apply_save_buttons, current_image_path, load_rgba, notify_saved
from Imervue.image.optimize import encode_to_budget
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.optimize_dialog")

_FORMATS = (("JPEG", ".jpg"), ("WEBP", ".webp"))


class _OptimizeWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, fmt: str, suffix: str, budget_kb: int, out_dir_path: str):
        super().__init__()
        self._path = path
        self._fmt = fmt
        self._suffix = suffix
        self._budget = budget_kb
        self._out = out_dir_path

    def run(self) -> None:
        try:
            data, _quality = encode_to_budget(load_rgba(self._path), self._budget, self._fmt)
            with open(self._out, "wb") as handle:
                handle.write(data)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Optimize failed: %s", exc)
            self.done.emit(False, str(exc))


class OptimizeDialog(QDialog):
    """Format + KB budget that re-encodes the current image to fit."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _OptimizeWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("optimize_title", "Optimize to Target Size"))
        self.setMinimumWidth(360)

        self._format = QComboBox()
        for fmt, suffix in _FORMATS:
            self._format.addItem(fmt, (fmt, suffix))
        self._budget = QSpinBox()
        self._budget.setRange(5, 50000)
        self._budget.setValue(200)
        self._budget.setSuffix(" KB")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("optimize_format", "Format:")))
        layout.addWidget(self._format)
        layout.addWidget(QLabel(lang.get("optimize_budget", "Target size:")))
        layout.addWidget(self._budget)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        fmt, suffix = self._format.currentData()
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_opt{suffix}")
        self._worker = _OptimizeWorker(
            self._path, fmt, suffix, self._budget.value(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "optimize_failed", "Optimize failed")
        if ok:
            self.accept()


def open_optimize(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        OptimizeDialog(viewer, path).exec()
