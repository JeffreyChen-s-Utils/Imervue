"""Tests for the auto-tag dialog's worker error-handling and thread lifecycle.

The worker must report a SQLite failure instead of hanging the progress bar; the
dialog must not launch a second run while one is in flight, and must tear the
worker thread down on close ("QThread: Destroyed while running").
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

from Imervue.gui import auto_tag_dialog
from Imervue.gui.auto_tag_dialog import AutoTagDialog, _AutoTagWorker


# ---------------------------------------------------------------------------
# _AutoTagWorker — always reports
# ---------------------------------------------------------------------------

def test_worker_emits_error_when_batch_raises(qapp, monkeypatch):
    def _boom(paths, progress_cb=None):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(auto_tag_dialog, "auto_tag_batch", _boom)
    worker = _AutoTagWorker(["a.png", "b.png"])
    errors: list = []
    dones: list = []
    worker.error.connect(errors.append)
    worker.done.connect(dones.append)
    worker.run()
    assert errors and "locked" in errors[0]
    assert dones == []


def test_worker_emits_done_on_success(qapp, monkeypatch):
    monkeypatch.setattr(auto_tag_dialog, "auto_tag_batch",
                        lambda paths, progress_cb=None: None)
    worker = _AutoTagWorker(["a.png", "b.png", "c.png"])
    dones: list = []
    worker.done.connect(dones.append)
    worker.run()
    assert dones == [3]


# ---------------------------------------------------------------------------
# Dialog thread lifecycle
# ---------------------------------------------------------------------------

class _FakeUi(QWidget):
    def __init__(self):
        super().__init__()
        self.viewer = SimpleNamespace(
            selected_tiles=set(), model=SimpleNamespace(images=["a.png"]))


def test_run_is_a_noop_while_a_run_is_in_flight(qapp):
    ui = _FakeUi()
    dlg = AutoTagDialog(ui)
    sentinel = object()
    dlg._worker = sentinel
    dlg._thread = SimpleNamespace(isRunning=lambda: True)
    dlg._run()                       # a second Run must be ignored
    assert dlg._worker is sentinel   # first run's worker not clobbered
    dlg._thread = None               # avoid touching the fake on teardown


def test_close_tears_down_a_running_thread(qapp):
    ui = _FakeUi()
    dlg = AutoTagDialog(ui)
    calls: list = []
    dlg._thread = SimpleNamespace(
        quit=lambda: calls.append("quit"),
        wait=lambda: calls.append("wait"),
        isRunning=lambda: True,
    )
    dlg._worker = object()
    dlg.close()
    assert calls == ["quit", "wait"]
    assert dlg._thread is None
    assert dlg._worker is None
