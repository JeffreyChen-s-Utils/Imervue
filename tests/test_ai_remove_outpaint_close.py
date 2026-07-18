"""AI object-remove / outpaint dialogs must stop their workers on reject/close.

Both started heavy QThreads (SAM encoder / diffusion inpaint) but tore down
only in closeEvent (or not at all), so Cancel — which delivers no closeEvent —
left the thread running and it was destroyed with the dialog ("QThread:
Destroyed while thread is still running"). They now inherit WorkerHostMixin.
"""
from __future__ import annotations

from types import SimpleNamespace

from ai_object_remove.ai_object_remove_plugin import ObjectRemoveDialog
from ai_outpaint.ai_outpaint_plugin import OutpaintDialog

_OBJ_ATTRS = ("_worker", "_sam_worker", "_mask_worker")


def _running(waited, name):
    return SimpleNamespace(
        isRunning=lambda: True,
        requestInterruption=lambda: None,
        disconnect=lambda: None,
        wait=lambda: waited.append(name),
    )


def test_object_remove_stops_all_three_workers():
    waited: list = []
    fake = SimpleNamespace(
        _worker_attrs=_OBJ_ATTRS,
        _worker=_running(waited, "remove"),
        _sam_worker=_running(waited, "sam"),
        _mask_worker=_running(waited, "mask"),
    )
    ObjectRemoveDialog._stop_worker(fake)
    assert set(waited) == {"remove", "sam", "mask"}
    assert fake._worker is None
    assert fake._sam_worker is None
    assert fake._mask_worker is None


def test_object_remove_skips_finished_workers():
    waited: list = []
    fake = SimpleNamespace(
        _worker_attrs=_OBJ_ATTRS,
        _worker=SimpleNamespace(isRunning=lambda: False, wait=lambda: waited.append("x")),
        _sam_worker=None,
        _mask_worker=None,
    )
    ObjectRemoveDialog._stop_worker(fake)
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
