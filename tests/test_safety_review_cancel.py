"""Cancel / teardown safety for the safety_review ("AI 打碼") plugin workers.

Cancel (reject) used to leave the detection QThread running and drop its
reference on a 5s wait timeout, destroying a live thread and crashing the
process (0xC0000409), most visibly on cancel-then-reuse. These pin the corrected
stop-worker behaviour and the subprocess terminate helper.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace


class _FakeProc:
    """Records the terminate/kill/wait calls it receives so the tests assert on
    call history (which the analyser can't constant-fold), not booleans."""

    def __init__(self, poll_val=None, wait_timeout=False):
        self._poll = poll_val
        self._wait_timeout = wait_timeout
        self.calls: list[str] = []

    def poll(self):
        return self._poll

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")

    def wait(self, timeout=None):
        self.calls.append("wait")
        if self._wait_timeout and timeout is not None:
            raise subprocess.TimeoutExpired("cmd", timeout)


class TestTerminateProcess:
    def test_none_is_noop(self):
        from safety_review._workers import _terminate_process
        _terminate_process(None)

    def test_already_exited_not_terminated(self):
        from safety_review._workers import _terminate_process
        proc = _FakeProc(poll_val=0)
        _terminate_process(proc)
        assert proc.calls == []                     # poll() not None -> untouched

    def test_running_is_terminated(self):
        from safety_review._workers import _terminate_process
        proc = _FakeProc(poll_val=None)
        _terminate_process(proc)
        assert "terminate" in proc.calls
        assert "kill" not in proc.calls

    def test_escalates_to_kill_on_timeout(self):
        from safety_review._workers import _terminate_process
        proc = _FakeProc(poll_val=None, wait_timeout=True)
        _terminate_process(proc)
        assert "kill" in proc.calls                 # terminate timed out -> killed


class _FakeWorker:
    def __init__(self, running: bool):
        self._running = running
        self.events: list[str] = []

    def isRunning(self):   # noqa: N802 - Qt API  # NOSONAR — mirrors QThread.isRunning
        return self._running

    def requestInterruption(self):   # noqa: N802 - Qt API  # NOSONAR — mirrors QThread.requestInterruption
        self.events.append("interrupt")

    def disconnect(self):
        self.events.append("disconnect")

    def wait(self):
        self.events.append("wait")


class TestStopWorker:
    def test_interrupts_waits_and_nulls_a_running_worker(self):
        from safety_review._dialogs import _WorkerHostMixin
        worker = _FakeWorker(running=True)
        host = SimpleNamespace(_worker=worker)
        _WorkerHostMixin._stop_worker(host)
        # Interruption requested and the thread waited on before the ref is
        # dropped — never dropped mid-run.
        assert worker.events == ["interrupt", "disconnect", "wait"]
        assert host._worker is None

    def test_idle_worker_just_nulled(self):
        from safety_review._dialogs import _WorkerHostMixin
        worker = _FakeWorker(running=False)
        host = SimpleNamespace(_worker=worker)
        _WorkerHostMixin._stop_worker(host)
        assert worker.events == []          # not running -> no wait
        assert host._worker is None

    def test_no_worker_is_safe(self):
        from safety_review._dialogs import _WorkerHostMixin
        host = SimpleNamespace(_worker=None)
        _WorkerHostMixin._stop_worker(host)
        assert host._worker is None


class TestManualStopDetectWorker:
    def test_interrupts_waits_and_nulls(self):
        from safety_review._manual_dialog import ManualReviewDialog
        worker = _FakeWorker(running=True)
        host = SimpleNamespace(_detect_worker=worker)
        ManualReviewDialog._stop_detect_worker(host)
        assert worker.events == ["interrupt", "disconnect", "wait"]
        assert host._detect_worker is None

    def test_no_worker_is_safe(self):
        from safety_review._manual_dialog import ManualReviewDialog
        host = SimpleNamespace(_detect_worker=None)
        ManualReviewDialog._stop_detect_worker(host)
        assert host._detect_worker is None


def test_batch_worker_breaks_on_interruption(qapp, monkeypatch):
    """A cancelled batch stops at its next per-image check instead of running to
    completion (so the caller's wait() returns promptly)."""
    from safety_review import _workers
    monkeypatch.setattr(_workers, "_resolve_detector", lambda mode: object())

    class _Interrupted(_workers._BatchWorker):
        def isInterruptionRequested(self):   # noqa: N802 - Qt API
            return True

    worker = _Interrupted(
        ["/a.png", "/b.png"], output_dir=None, block_size=8, padding=0,
        overwrite=False)
    results: list = []
    worker.result_ready.connect(lambda s, f, r: results.append((s, f, r)))
    worker.run()

    assert results == [(0, 0, 0)]   # broke before processing any image
