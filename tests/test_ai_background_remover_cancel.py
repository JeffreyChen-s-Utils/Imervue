"""Cancel / teardown safety for the ai_background_remover plugin dialogs.

The dialogs inherit the shared :class:`WorkerHostMixin` (covered by
``test_worker_host``); these pin the plugin-specific pieces the mixin relies on:
each subprocess worker's ``stop()`` terminate and the in-process batch worker's
interruption break.
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


def test_dialogs_use_the_shared_worker_host_mixin():
    from Imervue.plugin.worker_host import WorkerHostMixin
    from ai_background_remover.ai_background_remover import (
        BatchRemoveBackgroundDialog, RemoveBackgroundDialog,
    )
    assert issubclass(RemoveBackgroundDialog, WorkerHostMixin)
    assert issubclass(BatchRemoveBackgroundDialog, WorkerHostMixin)


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
