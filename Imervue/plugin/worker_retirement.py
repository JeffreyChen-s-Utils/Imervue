"""Retain cancelled QThreads and their hosts while stopping/joining off the UI thread."""
from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QThread, Qt, Slot
from shiboken6 import isValid

from Imervue.system.qt_timers import call_later

logger = logging.getLogger("Imervue.worker_host")
_RETIRING: set[WorkerRetirement] = set()
_SHUTDOWN_CONNECTED = False


def _drain_on_exit() -> None:
    """Join remaining retirement threads only at final application event-loop exit."""
    for retirement in tuple(_RETIRING):
        retirement.wait()


class WorkerRetirement(QThread):
    """Keep workers/owner alive until cancellation hooks and actual thread exit complete."""

    def __init__(self, owner, workers: list[QThread], completed: Callable[[], None], *,
                 cancel: bool = True) -> None:
        super().__init__()
        self._owner = owner
        self._workers = workers
        self._completed = completed
        self._cancel = cancel
        owner.destroyed.connect(self._owner_destroyed)
        self.finished.connect(self._finish, Qt.ConnectionType.QueuedConnection)
        for worker in workers:
            worker.setParent(self)

    @Slot()
    def _owner_destroyed(self) -> None:
        self._owner = self._completed = None

    def run(self) -> None:
        for worker in self._workers if self._cancel else ():
            for name in ("stop", "abort"):
                cancel = getattr(worker, name, None)
                if callable(cancel):
                    try:
                        cancel()
                    except Exception:  # a failing plugin hook must not skip the lifetime join
                        logger.exception("Worker cancellation hook failed: %s", name)
        for worker in self._workers:
            worker.wait()

    @Slot()
    def _finish(self) -> None:
        # QThread.finished precedes TLS destruction. Never delete a live reaper
        # or wait for its TLS cleanup on the UI thread.
        if not self.wait(0):
            call_later(10, self, self._finish)
            return
        owner, completed = self._owner, self._completed
        self._owner = self._completed = None
        try:
            if owner is not None and isValid(owner):
                owner.destroyed.disconnect(self._owner_destroyed)
                completed()
        finally:
            for worker in self._workers:
                if isValid(worker):
                    worker.deleteLater()
            self._workers.clear()
            _RETIRING.discard(self)
            self.deleteLater()


def retire_workers(owner, workers: list[QThread], completed: Callable[[], None], *,
                   cancel: bool = True) -> None:
    """Start nonblocking retirement; cancellation hooks may themselves perform blocking I/O."""
    global _SHUTDOWN_CONNECTED
    if not _SHUTDOWN_CONNECTED:
        QCoreApplication.instance().aboutToQuit.connect(_drain_on_exit)
        _SHUTDOWN_CONNECTED = True
    retirement = WorkerRetirement(owner, workers, completed, cancel=cancel)
    _RETIRING.add(retirement)
    retirement.start()
