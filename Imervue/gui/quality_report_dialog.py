"""Quality-report dialog — no-reference metrics for the current image.

Pure analysis in :mod:`Imervue.image.quality_metrics`; this dialog renders the
metric name→value table read-only.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import current_image_path, load_rgba
from Imervue.image.quality_metrics import quality_metrics
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class QualityReportDialog(QDialog):
    """Read-only no-reference quality metrics for one image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("quality_title", "Quality Report"))
        self.setMinimumWidth(360)

        metrics = quality_metrics(load_rgba(path))
        self._table = QTableWidget(len(metrics), 1)
        self._table.setHorizontalHeaderLabels([lang.get("quality_value", "Value")])
        self._table.setVerticalHeaderLabels([
            lang.get(f"quality_{name}", name.replace("_", " ").title()) for name in metrics
        ])
        for row, name in enumerate(metrics):
            self._table.setItem(row, 0, QTableWidgetItem(f"{metrics[name]:.3f}"))
        self._table.resizeColumnsToContents()

        close = QPushButton(lang.get("export_cancel", "Close"))
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(buttons)


def open_quality_report(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        QualityReportDialog(viewer, path).exec()
