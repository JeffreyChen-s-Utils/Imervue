"""Tests for the shared WorkerHostMixin dialog teardown.

``_stop_worker`` is exercised against fake workers without a QApplication (it
only calls duck-typed QThread methods); a small Qt smoke test confirms reject()
and closeEvent() both route through it.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.plugin.worker_host import WorkerHostMixin


class _FakeWorker:
    def __init__(self, running: bool, has_stop: bool = False):
        self._running = running
        self.events: list[str] = []
        if has_stop:
            self.stop = lambda: self.events.append("stop")

    def isRunning(self):   # noqa: N802 - Qt API  # NOSONAR — mirrors QThread.isRunning
        return self._running

    def requestInterruption(self):   # noqa: N802 - Qt API  # NOSONAR — mirrors QThread.requestInterruption
        self.events.append("interrupt")

    def disconnect(self):
        self.events.append("disconnect")

    def wait(self, timeout=None):
        self.events.append("wait")


class TestStopWorker:
    def test_running_worker_interrupted_disconnected_waited_nulled(self):
        worker = _FakeWorker(running=True)
        host = SimpleNamespace(_worker=worker)
        WorkerHostMixin._stop_worker(host)
        assert worker.events == ["interrupt", "disconnect", "wait"]
        assert host._worker is None

    def test_worker_with_stop_is_stopped_before_wait(self):
        worker = _FakeWorker(running=True, has_stop=True)
        host = SimpleNamespace(_worker=worker)
        WorkerHostMixin._stop_worker(host)
        assert worker.events == ["interrupt", "stop", "disconnect", "wait"]
        assert host._worker is None

    def test_worker_with_abort_is_aborted_before_wait(self):
        worker = _FakeWorker(running=True)
        worker.abort = lambda: worker.events.append("abort")
        host = SimpleNamespace(_worker=worker)
        WorkerHostMixin._stop_worker(host)
        assert worker.events == ["interrupt", "abort", "disconnect", "wait"]
        assert host._worker is None

    def test_idle_worker_just_nulled(self):
        worker = _FakeWorker(running=False)
        host = SimpleNamespace(_worker=worker)
        WorkerHostMixin._stop_worker(host)
        assert worker.events == []
        assert host._worker is None

    def test_none_worker_is_safe(self):
        host = SimpleNamespace(_worker=None)
        WorkerHostMixin._stop_worker(host)
        assert host._worker is None

    def test_missing_attr_is_safe(self):
        host = SimpleNamespace()
        WorkerHostMixin._stop_worker(host)      # must not raise
        assert getattr(host, "_worker", None) is None

    def test_multiple_worker_attrs_all_stopped(self):
        primary = _FakeWorker(running=True)
        secondary = _FakeWorker(running=True)
        host = SimpleNamespace(
            _worker_attrs=("_worker", "_aux"),
            _worker=primary, _aux=secondary,
        )
        WorkerHostMixin._stop_worker(host)
        assert primary.events == ["interrupt", "disconnect", "wait"]
        assert secondary.events == ["interrupt", "disconnect", "wait"]
        assert host._worker is None
        assert host._aux is None


def test_reject_and_close_route_through_stop_worker(qapp):
    """A concrete dialog subclass stops its worker on BOTH Cancel and close."""
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QDialog

    class _Dialog(WorkerHostMixin, QDialog):
        def __init__(self):
            super().__init__(None)
            self._worker = _FakeWorker(running=True)

    dlg = _Dialog()
    worker = dlg._worker
    dlg.reject()
    assert worker.events == ["interrupt", "disconnect", "wait"]
    assert dlg._worker is None

    dlg2 = _Dialog()
    worker2 = dlg2._worker
    dlg2.closeEvent(QCloseEvent())
    assert worker2.events == ["interrupt", "disconnect", "wait"]
    assert dlg2._worker is None
