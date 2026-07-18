"""Cancel / teardown safety for the ai_background_remover plugin dialogs.

Cancel (reject) used to bypass the closeEvent-only cleanup and leave the rembg
QThread running; the closeEvent path itself dropped the reference on a 5s wait
timeout, destroying a live thread and crashing the process (0xC0000409),
most visibly on cancel-then-reuse. These pin the corrected stop-worker
behaviour, the subprocess ``stop()`` terminate, and the batch interruption
break.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace


class _FakeProc:
    def __init__(self, poll_val=None):
        self._poll = poll_val
        self.calls: list[str] = []

    def poll(self):
        return self._poll

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")

    def wait(self, timeout=None):
        self.calls.append("wait")


class _FakeWorker:
    def __init__(self, running: bool, has_stop: bool = False):
        self._running = running
        self.events: list[str] = []
        if has_stop:
            self.stop = lambda: self.events.append("stop")

    def isRunning(self):   # noqa: N802 - Qt API
        return self._running

    def requestInterruption(self):   # noqa: N802 - Qt API
        self.events.append("interrupt")

    def disconnect(self):
        self.events.append("disconnect")

    def wait(self, timeout=None):
        self.events.append("wait")


class TestStopWorker:
    def test_interrupts_stops_waits_and_nulls_a_running_worker(self):
        from ai_background_remover.ai_background_remover import _WorkerHostDialog
        worker = _FakeWorker(running=True, has_stop=True)
        host = SimpleNamespace(_worker=worker)
        _WorkerHostDialog._stop_worker(host)
        # Child terminated (stop) before the thread is waited on, and the ref is
        # dropped only after wait() — never mid-run.
        assert worker.events == ["interrupt", "stop", "disconnect", "wait"]
        assert host._worker is None

    def test_running_worker_without_stop_still_torn_down(self):
        from ai_background_remover.ai_background_remover import _WorkerHostDialog
        worker = _FakeWorker(running=True, has_stop=False)
        host = SimpleNamespace(_worker=worker)
        _WorkerHostDialog._stop_worker(host)
        assert worker.events == ["interrupt", "disconnect", "wait"]
        assert host._worker is None

    def test_idle_worker_just_nulled(self):
        from ai_background_remover.ai_background_remover import _WorkerHostDialog
        worker = _FakeWorker(running=False)
        host = SimpleNamespace(_worker=worker)
        _WorkerHostDialog._stop_worker(host)
        assert worker.events == []          # not running -> no wait
        assert host._worker is None

    def test_no_worker_is_safe(self):
        from ai_background_remover.ai_background_remover import _WorkerHostDialog
        host = SimpleNamespace(_worker=None)
        _WorkerHostDialog._stop_worker(host)
        assert host._worker is None

    def test_missing_worker_attr_is_safe(self):
        from ai_background_remover.ai_background_remover import _WorkerHostDialog
        host = SimpleNamespace()             # no _worker attribute at all
        _WorkerHostDialog._stop_worker(host)   # must not raise
        assert getattr(host, "_worker", None) is None


class TestSubprocessWorkerStop:
    def test_single_worker_stop_terminates_child(self):
        from ai_background_remover.ai_background_remover import _SubprocessRemoveWorker
        proc = _FakeProc(poll_val=None)
        host = SimpleNamespace(_proc=proc)
        _SubprocessRemoveWorker.stop(host)
        assert "terminate" in proc.calls

    def test_batch_worker_stop_is_noop_without_child(self):
        from ai_background_remover.ai_background_remover import _SubprocessBatchWorker
        host = SimpleNamespace(_proc=None)
        _SubprocessBatchWorker.stop(host)    # must not raise


def _install_fake_ml_modules(monkeypatch):
    fake_rembg = types.ModuleType("rembg")
    fake_rembg.remove = lambda *a, **k: None
    fake_rembg.new_session = lambda *a, **k: object()
    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = types.SimpleNamespace(
        open=lambda *a, **k: None, fromarray=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "rembg", fake_rembg)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)


def test_batch_worker_breaks_on_interruption(qapp, monkeypatch):
    """A cancelled in-process batch stops at its first per-image check instead
    of running to completion, so the caller's wait() returns promptly."""
    from ai_background_remover.ai_background_remover import _BatchRemoveWorker
    _install_fake_ml_modules(monkeypatch)

    class _Interrupted(_BatchRemoveWorker):
        def isInterruptionRequested(self):   # noqa: N802 - Qt API
            return True

    worker = _Interrupted(
        ["/a.png", "/b.png"], output_dir="/out", model_name="u2net",
        alpha_matting=False)
    results: list = []
    worker.result_ready.connect(lambda s, f: results.append((s, f)))
    worker.run()

    assert results == [(0, 0)]   # broke before processing any image
