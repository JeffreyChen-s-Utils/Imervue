"""Application-owned task registry and a shared, modeless result/cancellation panel."""

from __future__ import annotations

import logging
import json
from collections.abc import Callable
from dataclasses import dataclass, asdict
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QThread,
    QTimer,
    Signal,
    QUrl,
    Qt,
    QSignalBlocker,
)
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

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.job_state import JobState, TERMINAL
from Imervue.system.atomic_write import write_text_atomically

logger = logging.getLogger("Imervue.jobs")
RetryFactory = Callable[[tuple[str, ...]], QThread]
_VISIBLE_RESULTS = 500


@dataclass
class Job:
    """Retain work until actual thread exit; retry factories capture settings, never dialogs."""

    title: str
    state: JobState
    worker: QThread | None
    retry_factory: RetryFactory | None = None
    owned: bool = False
    retry_started: bool = False

    @property
    def settled(self) -> bool:
        """True only after the registry observes actual worker exit."""
        return self.worker is None


class JobRegistry(QObject):
    """Keep cross-window progress and results independently of originating dialogs."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.jobs: list[Job] = []
        self._last = ()
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.poll)
        QCoreApplication.instance().aboutToQuit.connect(self.drain)

    def add(
        self,
        worker: QThread,
        title: str,
        retry_factory: RetryFactory | None = None,
        *,
        owned: bool = False,
    ) -> Job:
        """Register before start; callers retain existing worker/dialog ownership contracts."""
        if not isinstance(worker, QThread) or not isinstance(
            getattr(worker, "job_state", None), JobState
        ):
            raise TypeError("A background job requires a QThread with JobState")
        # A Python reference does not protect a child QThread from its QWidget
        # parent's C++ destruction. The registry retains the unparented thread
        # until actual exit, even when the originating dialog is deleted.
        worker.setParent(None)
        job = Job(title, worker.job_state, worker, retry_factory, owned)
        self.jobs.append(job)
        self._timer.start()
        self.changed.emit()
        return job

    def add_completed(self, title: str, state: JobState) -> Job:
        """Retain synchronous output results in the same cross-window report/open panel."""
        if (not isinstance(state, JobState)
                or state.snapshot(include_items=False).status not in TERMINAL):
            raise ValueError("A completed result requires terminal JobState")
        job = Job(title, state, None)
        self.jobs.append(job)
        self.changed.emit()
        return job

    def poll(self) -> None:
        """Poll immutable progress, retaining finishing threads until wait(0) succeeds."""
        for job in self.jobs:
            worker = job.worker
            if worker is None:
                continue
            terminal = job.state.snapshot(include_items=False).status in TERMINAL
            if not isValid(worker) or ((worker.isFinished() or terminal) and worker.wait(0)):
                job.state.finish()
                job.worker = None
                if job.owned and isValid(worker):
                    worker.deleteLater()
        summary = tuple((job.state.snapshot(include_items=False), job.settled) for job in self.jobs)
        if summary != self._last:
            self._last = summary
            self.changed.emit()
        if all(job.settled for job in self.jobs):
            self._timer.stop()

    def cancel(self, job: Job) -> None:
        """Request cooperative cancellation; an uninterruptible operation remains retained."""
        if not job.settled:
            job.state.request_cancel()
            if isValid(job.worker):
                job.worker.requestInterruption()
            self.changed.emit()

    def retry(self, job: Job) -> Job | None:
        """Start a new job for failures once; never re-export successful outputs."""
        paths = job.state.failed_paths()
        if not job.settled or job.retry_started or not paths or job.retry_factory is None:
            return None
        try:
            worker = job.retry_factory(paths)
            following = self.add(worker, job.title, job.retry_factory, owned=True)
        except Exception:  # plugin factory boundary; keep the original retry available
            logger.exception("Unable to restart background job")
            return None
        job.retry_started = True
        worker.start()
        return following

    def clear_finished(self) -> None:
        """Release finished result histories and captured retry settings explicitly."""
        self.jobs = [job for job in self.jobs if not job.settled]
        self.changed.emit()

    def drain(self) -> None:
        """Join surviving work only at final application exit."""
        for job in self.jobs:
            if job.worker is not None and isValid(job.worker):
                job.state.request_cancel()
                job.worker.requestInterruption()
                job.worker.wait()


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


class BackgroundJobsDialog(QDialog):
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

    def _selected(self) -> Job | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        return (item.parent() or item).data(0, Qt.ItemDataRole.UserRole)

    def refresh(self) -> None:
        """Rebuild summaries; expand only the selected job's potentially large result list."""
        selected = self._selected()
        blocker = QSignalBlocker(self.tree)
        self.tree.clear()
        for job in self._registry.jobs:
            snap = job.state.snapshot(include_items=False)
            status = snap.status if job.settled or snap.status not in TERMINAL else "finishing"
            root = QTreeWidgetItem(
                [job.title, self._text(f"jobs_{status}", status), f"{snap.current}/{snap.total}"]
            )
            root.setData(0, Qt.ItemDataRole.UserRole, job)
            self.tree.addTopLevelItem(root)
            if job is selected:
                self.tree.setCurrentItem(root)
                self._details(root, job)
        blocker.unblock()
        self._buttons()

    def _details(self, root: QTreeWidgetItem, job: Job) -> None:
        results, total = job.state.visible_results(_VISIBLE_RESULTS)
        for result in results:
            child = QTreeWidgetItem(
                [
                    result.source,
                    self._text(f"jobs_{result.status}", result.status),
                    result.error or result.output,
                ]
            )
            child.setData(1, Qt.ItemDataRole.UserRole, result.output)
            for column in range(3):
                child.setToolTip(column, child.text(column))
            root.addChild(child)
        if total > _VISIBLE_RESULTS:
            root.addChild(
                QTreeWidgetItem(
                    [
                        self._text("jobs_more", "More results are available in the full report"),
                        "",
                        "",
                    ]
                )
            )
        root.setExpanded(True)

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

    def _buttons(self) -> None:
        job = self._selected()
        self.cancel_button.setEnabled(job is not None and not job.settled)
        self.retry_button.setEnabled(
            job is not None
            and job.settled
            and not job.retry_started
            and job.retry_factory is not None
            and bool(job.state.failed_paths())
        )
        item = self.tree.currentItem()
        if (
            job is not None
            and item is not None
            and item.parent() is None
            and item.childCount() == 0
        ):
            self._details(item, job)

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
