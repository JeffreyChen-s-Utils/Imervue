"""Application-owned task registry and a shared, modeless result/cancellation panel."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from shiboken6 import isValid

from Imervue.gui.background_jobs_registry import Job, JobRegistry, RetryFactory, logger
from Imervue.gui.background_jobs_rows import JobRowsMixin
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.atomic_write import write_text_atomically

__all__ = [
    "BackgroundJobsDialog",
    "Job",
    "JobRegistry",
    "RetryFactory",
    "drain_background_jobs",
    "job_registry",
    "open_background_jobs",
]


def job_registry() -> JobRegistry:
    """One registry per QApplication, shared by every viewer window."""
    app = QCoreApplication.instance()
    registry = getattr(app, "_imervue_jobs", None)
    if registry is None:
        registry = JobRegistry(app)
        app._imervue_jobs = registry
    return registry


def drain_background_jobs() -> None:
    """Finish retained work before the last-window process-exit path bypasses Qt shutdown."""
    app = QCoreApplication.instance()
    registry = getattr(app, "_imervue_jobs", None)
    if registry is not None:
        registry.drain()


class BackgroundJobsDialog(JobRowsMixin, QDialog):
    """Select a task for detailed outputs/errors; double-click a successful output to open it."""

    def __init__(self, parent=None, *, registry: JobRegistry | None = None) -> None:
        super().__init__(parent)
        self._registry = registry or job_registry()
        self._lang = language_wrapper.language_word_dict
        self.setWindowTitle(self._text("background_jobs", "Background Jobs"))
        self.resize(800, 480)
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            [
                self._text("jobs_task", "Task"),
                self._text("jobs_status", "Status"),
                self._text("jobs_details", "Output / failure"),
            ]
        )
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 120)
        self.tree.itemSelectionChanged.connect(self._buttons)
        self.tree.itemDoubleClicked.connect(self._open_output)
        layout.addWidget(self.tree)
        row = QHBoxLayout()
        self.cancel_button = QPushButton(self._text("export_cancel", "Cancel"))
        self.retry_button = QPushButton(self._text("jobs_retry_failed", "Retry failed items"))
        clear = QPushButton(self._text("jobs_clear", "Clear finished"))
        report = QPushButton(self._text("jobs_save_report", "Save full report"))
        report.clicked.connect(self._save_report)
        self.cancel_button.clicked.connect(self._cancel)
        self.retry_button.clicked.connect(self._retry)
        clear.clicked.connect(self._registry.clear_finished)
        for button in (self.cancel_button, self.retry_button, clear, report):
            row.addWidget(button)
        layout.addLayout(row)
        self._registry.changed.connect(self.refresh)
        self.refresh()

    def _text(self, key: str, fallback: str) -> str:
        return self._lang.get(key, fallback)

    def _save_report(self) -> None:
        job = self._selected()
        if job is None:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, self._text("jobs_save_report", "Save full report"), "", "JSON (*.json)"
        )
        if path:
            try:
                write_text_atomically(
                    Path(path),
                    json.dumps(
                        {"title": job.title, **asdict(job.state.snapshot())},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            except OSError as exc:
                logger.exception("Unable to save job report")
                QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _cancel(self) -> None:
        job = self._selected()
        if job is not None:
            self._registry.cancel(job)

    def _retry(self) -> None:
        job = self._selected()
        if job is not None:
            self._registry.retry(job)

    def _open_output(self, item: QTreeWidgetItem, _column: int) -> None:
        output = item.data(1, Qt.ItemDataRole.UserRole)
        if output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(output))


def open_background_jobs(ui) -> None:
    """Show one modeless panel per window with shared application results."""
    dialog = getattr(ui, "_background_jobs_dialog", None)
    if dialog is None or not isValid(dialog):
        dialog = BackgroundJobsDialog(ui)
        ui._background_jobs_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
