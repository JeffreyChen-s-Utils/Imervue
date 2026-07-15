"""The auto-straighten dialog must never orphan a running worker.

Detect and Apply share ``self._worker``. Starting one while the other is
still mid-flight used to reassign ``self._worker`` and drop the only Python
reference to the running QThread, so shiboken deleted the C++ thread while it
ran ("QThread: Destroyed while thread is still running" -> abort). The dialog
now guards both entry points on the worker's ``isRunning()`` and waits it on
close. These tests drive the methods unbound on fakes -- no Qt widget, no cv2.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.auto_straighten_dialog import AutoStraightenDialog


def _running_worker():
    return SimpleNamespace(isRunning=lambda: True)


def _finished_worker():
    return SimpleNamespace(isRunning=lambda: False)


def test_worker_busy_true_only_while_running():
    assert AutoStraightenDialog._worker_busy(
        SimpleNamespace(_worker=_running_worker())) is True
    assert AutoStraightenDialog._worker_busy(
        SimpleNamespace(_worker=_finished_worker())) is False
    assert AutoStraightenDialog._worker_busy(
        SimpleNamespace(_worker=None)) is False


def test_detect_is_noop_while_a_worker_runs():
    running = _running_worker()
    calls = []
    fake = SimpleNamespace(
        _worker=running,
        _worker_busy=lambda: True,
        _set_running=lambda v: calls.append(v),
        _progress=SimpleNamespace(setVisible=lambda v: None),
        _path="x.png",
    )
    AutoStraightenDialog._detect(fake)
    # Guard returned early: the running worker is untouched and nothing was
    # re-armed, so no second QThread was ever constructed.
    assert fake._worker is running
    assert calls == []


def test_apply_is_noop_while_a_worker_runs():
    running = _running_worker()
    calls = []
    fake = SimpleNamespace(
        _worker=running,
        _worker_busy=lambda: True,
        _set_running=lambda v: calls.append(v),
        _progress=SimpleNamespace(setVisible=lambda v: None),
        _out_edit=SimpleNamespace(text=lambda: "out.png"),
        _angle=SimpleNamespace(value=lambda: 1.0),
        _path="x.png",
    )
    AutoStraightenDialog._apply(fake)
    assert fake._worker is running
    assert calls == []


def test_wait_worker_blocks_on_a_running_worker():
    waited = []
    worker = SimpleNamespace(isRunning=lambda: True,
                             wait=lambda: waited.append(True))
    fake = SimpleNamespace(_worker=worker, _worker_busy=lambda: True)
    AutoStraightenDialog._wait_worker(fake)
    assert waited == [True]


def test_wait_worker_skips_a_finished_worker():
    waited = []
    worker = SimpleNamespace(isRunning=lambda: False,
                             wait=lambda: waited.append(True))
    fake = SimpleNamespace(_worker=worker, _worker_busy=lambda: False)
    AutoStraightenDialog._wait_worker(fake)
    assert waited == []


def test_wait_worker_handles_no_worker():
    fake = SimpleNamespace(_worker=None, _worker_busy=lambda: False)
    AutoStraightenDialog._wait_worker(fake)  # must not raise
