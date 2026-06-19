"""Image-statistics dialog — per-channel readout + histogram CSV export.

Pure analysis in :mod:`Imervue.image.statistics`; this dialog shows the
per-channel table and writes the 256-bin histogram to CSV on request.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import current_image_path, load_rgba
from Imervue.image.statistics import histogram_csv, image_statistics
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.image_statistics_dialog")

_METRICS = ("mean", "min", "max", "std", "median")


class ImageStatisticsDialog(QDialog):
    """Read-only per-channel statistics with a histogram-CSV export button."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._arr = load_rgba(path)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("stats_title", "Image Statistics"))
        self.setMinimumWidth(420)

        self._table = self._build_table(image_statistics(self._arr))
        export = QPushButton(lang.get("stats_export_csv", "Export Histogram CSV…"))
        export.clicked.connect(self._export_csv)
        close = QPushButton(lang.get("export_cancel", "Close"))
        close.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(export)
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(buttons)

    def _build_table(self, stats: dict) -> QTableWidget:
        channels = list(stats)
        table = QTableWidget(len(channels), len(_METRICS))
        table.setHorizontalHeaderLabels([m.title() for m in _METRICS])
        table.setVerticalHeaderLabels([c.upper() for c in channels])
        for row, channel in enumerate(channels):
            for col, metric in enumerate(_METRICS):
                table.setItem(row, col, QTableWidgetItem(f"{stats[channel][metric]:.2f}"))
        table.resizeColumnsToContents()
        return table

    def _export_csv(self) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        default = str(Path(self._path).with_suffix(".histogram.csv"))
        out, _ = QFileDialog.getSaveFileName(
            self, lang.get("stats_export_csv", "Export Histogram CSV…"), default, "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8", newline="") as handle:
            handle.write(histogram_csv(self._arr))
        toast = getattr(getattr(self._viewer, "main_window", None), "toast", None)
        if toast is not None:
            toast.info(lang.get("stats_exported", "Saved {path}").format(path=Path(out).name))


def open_image_statistics(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        ImageStatisticsDialog(viewer, path).exec()
