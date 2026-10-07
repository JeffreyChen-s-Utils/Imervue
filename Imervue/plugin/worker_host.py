"""Nonblocking dialog cancellation with completion-based QThread ownership.

Cancel/OK/window-close first disconnect worker output and request interruption.
Actual stop/abort hooks and joins run on a retirement thread. The dialog stays
disabled with cancellation status until all workers exit, then completes the
original result. This prevents both UI stalls and destruction of live QThreads.
"""
from __future__ import annotations

import contextlib

from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QDialog

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.worker_retirement import retire_workers

_DEFAULT_WORKER_ATTRS = ("_worker",)


def _stop_and_null(host: object, attr: str) -> QThread | None:
    """Detach one worker; real threads are returned for background retirement."""
    worker = getattr(host, attr, None)
    if worker is None:
        return None
    running = worker.isRunning()
    if running:
        worker.requestInterruption()
    if isinstance(worker, QThread) and (running or not worker.wait(0)):
        QObject.disconnect(worker, None, None, None)
        setattr(host, attr, None)
        return worker
    if running:
        # Non-Qt adapters retain their synchronous duck-typed teardown contract.
        for name in ("stop", "abort"):
            cancel = getattr(worker, name, None)
            if callable(cancel):
                cancel()
        with contextlib.suppress(RuntimeError, TypeError):
            worker.disconnect()
        worker.wait()
    setattr(host, attr, None)
    return None


class WorkerHostMixin:
    """List before QDialog; keep worker attributes until completion or retirement.

    ``stop`` and ``abort`` hooks run off the UI thread and must only cancel work
    (thread-safe flags or subprocess control), never access GUI widgets. Dialog
    completion is deferred while cancelling; the first requested result wins.
    ``_stop_worker`` also supports existing non-Qt test/adaptor hosts.
    """

    _worker_attrs: tuple[str, ...] = _DEFAULT_WORKER_ATTRS

    def _stop_worker(self) -> bool:
        """Request cancellation without UI waits; return whether retirement is pending."""
        if getattr(self, "_worker_retiring", False):
            return True
        workers = []
        for attr in getattr(self, "_worker_attrs", _DEFAULT_WORKER_ATTRS):
            worker = _stop_and_null(self, attr)
            if worker is not None and worker not in workers:
                workers.append(worker)
        if not workers:
            return False
        self._retire_workers(workers)
        return True

    def _retire_workers(self, workers: list[QThread], *, cancel: bool = True) -> None:
        """Keep a disabled owner until actual thread exit, including custom done packets."""
        self._worker_retiring = True
        self._worker_previous_enabled = self.isEnabled()
        self._worker_previous_title = self.windowTitle()
        self.setEnabled(False)
        lang = language_wrapper.language_word_dict
        text = (lang.get("worker_cancelling", "Cancelling…") if cancel
                else lang.get("worker_finishing", "Finishing…"))
        self.setWindowTitle(f"{self._worker_previous_title} — {text}")
        retire_workers(self, workers, self._worker_retired, cancel=cancel)

    def _worker_retired(self) -> None:
        self._worker_retiring = False
        self.setEnabled(self._worker_previous_enabled)
        self.setWindowTitle(self._worker_previous_title)
        result = getattr(self, "_worker_close_result", None)
        self._worker_close_result = None
        if result is not None:
            super().done(result)

    def done(self, result: int) -> None:
        """Finish once actual workers exit, retaining the first requested dialog result."""
        if getattr(self, "_worker_retiring", False):
            if getattr(self, "_worker_close_result", None) is None:
                self._worker_close_result = result
            return
        self._worker_close_result = result
        if not self._stop_worker():
            self._worker_close_result = None
            super().done(result)

    def closeEvent(self, event):  # noqa: N802 - Qt API  # NOSONAR — QWidget override
        self.done(QDialog.DialogCode.Rejected)
        if getattr(self, "_worker_retiring", False):
            event.ignore()
        else:
            super().closeEvent(event)
