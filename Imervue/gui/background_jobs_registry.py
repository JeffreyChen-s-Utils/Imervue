"""Application-owned task registry: retains workers until actual exit and retries failures."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QObject, QThread, QTimer, Signal
from shiboken6 import isValid

from Imervue.system.job_state import JobState, TERMINAL

logger = logging.getLogger("Imervue.jobs")
RetryFactory = Callable[[tuple[str, ...]], QThread]


@dataclass
class Job:
    """Retain work until actual thread exit; retry factories capture settings, never dialogs."""

    title: str
    state: JobState
    worker: QThread | None
    retry_factory: RetryFactory | None = None
    owned: bool = False
    retry_started: bool = False
    cancel_callback: Callable[[], object] | None = None

    @property
    def settled(self) -> bool:
        """True only after the registry observes actual worker exit."""
        return self.worker is None and self.state.snapshot(include_items=False).status in TERMINAL

    def poll(self) -> None:
        """Release a worker only after its actual exit, or a completed activity's callback."""
        worker = self.worker
        if worker is None:
            if self.settled:
                self.cancel_callback = None
            return
        terminal = self.state.snapshot(include_items=False).status in TERMINAL
        if not isValid(worker) or ((worker.isFinished() or terminal) and worker.wait(0)):
            self.state.finish()
            self.worker = None
            if self.owned and isValid(worker):
                worker.deleteLater()


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

    def add_activity(self, title: str, state: JobState, cancel: Callable[[], object]) -> Job:
        """Track a GUI-owned recording until its completion signal finishes the state."""
        if state.snapshot(include_items=False).status in TERMINAL:
            raise ValueError("An activity requires a running JobState")
        job = Job(title, state, None, cancel_callback=cancel)
        self.jobs.append(job)
        self._timer.start()
        self.changed.emit()
        return job

    def poll(self) -> None:
        """Poll immutable progress, retaining finishing threads until wait(0) succeeds."""
        for job in self.jobs:
            job.poll()
        summary = tuple((job.state.snapshot(include_items=False), job.settled) for job in self.jobs)
        if summary != self._last:
            self._last = summary
            self.changed.emit()
        if all(job.settled for job in self.jobs):
            self._timer.stop()

    def cancel(self, job: Job) -> None:
        """Request cooperative cancellation; an uninterruptible operation remains retained."""
        if not job.settled:
            if job.worker is None and job.cancel_callback is not None:
                job.cancel_callback()
            else:
                job.state.request_cancel()
                if job.worker is not None and isValid(job.worker):
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
            elif not job.settled and job.cancel_callback is not None:
                job.cancel_callback()
