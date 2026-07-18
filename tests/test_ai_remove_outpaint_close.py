"""AI object-remove / outpaint dialogs must wait their workers on close.

Both started heavy QThreads (SAM encoder / diffusion inpaint) but had no
closeEvent, so closing mid-run destroyed the thread ("QThread: Destroyed while
thread is still running").
"""
from __future__ import annotations

from types import SimpleNamespace

from ai_object_remove.ai_object_remove_plugin import ObjectRemoveDialog
from ai_outpaint.ai_outpaint_plugin import OutpaintDialog


def _running(waited, name):
    return SimpleNamespace(
        isRunning=lambda: True,
        requestInterruption=lambda: None,
        disconnect=lambda: None,
        wait=lambda: waited.append(name),
    )


def test_object_remove_waits_both_workers():
    waited: list = []
    fake = SimpleNamespace(
        _worker=_running(waited, "remove"),
        _sam_worker=_running(waited, "sam"),
        _mask_worker=_running(waited, "mask"),
    )
    ObjectRemoveDialog._wait_workers(fake)
    assert set(waited) == {"remove", "sam", "mask"}


def test_object_remove_skips_finished_workers():
    waited: list = []
    fake = SimpleNamespace(
        _worker=SimpleNamespace(isRunning=lambda: False, wait=lambda: waited.append("x")),
        _sam_worker=None,
        _mask_worker=None,
    )
    ObjectRemoveDialog._wait_workers(fake)
    assert waited == []


def test_outpaint_stops_running_worker():
    # OutpaintDialog now inherits WorkerHostMixin; _stop_worker joins the worker.
    waited: list = []
    host = SimpleNamespace(_worker=_running(waited, "out"))
    OutpaintDialog._stop_worker(host)
    assert waited == ["out"]
    assert host._worker is None


def test_outpaint_is_safe_without_a_worker():
    OutpaintDialog._stop_worker(SimpleNamespace(_worker=None))   # must not raise
