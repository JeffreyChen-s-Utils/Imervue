"""The GIF/Video dialog must honour Cancel, never destroy a live worker, and
report a single outcome.

Cancel was wired straight to ``reject`` while ``_CreateWorker`` kept encoding;
there was no ``closeEvent`` so quitting mid-encode destroyed the running QThread
("QThread: Destroyed while thread is still running" -> abort); and the video
path emitted a failure and then ``run`` emitted a *success* on top of it, so a
missing ffmpeg was masked as "done". The worker now aborts cleanly, raises on
error so ``run`` emits exactly one terminal result, and the dialog aborts+waits
on close.

Worker tests run ``run()`` directly under ``qapp``; dialog tests drive the
methods unbound on fakes -- no widget constructed.
"""
from __future__ import annotations

import shutil
from types import SimpleNamespace

from Imervue.gui.gif_video_dialog import GifVideoDialog, _CreateWorker


def test_create_worker_abort_emits_cancelled(qapp):
    results: list = []
    worker = _CreateWorker(["a.png"], "/out.gif", "GIF", 10, 0, 0, True)
    worker.result_ready.connect(lambda ok, msg: results.append((ok, msg)))
    worker.abort()
    worker.run()   # aborted before the first frame -> no file, cancelled result
    assert results == [(False, "cancelled")]


def test_missing_ffmpeg_emits_exactly_one_failure(qapp, monkeypatch):
    # Regression: the video path used to emit (False, "ffmpeg not found") and
    # then run() emitted (True, output) on top, masking the failure as success.
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    results: list = []
    worker = _CreateWorker(["a.png"], "/out.mp4", "MP4", 24, 0, 0, True)
    worker.result_ready.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert len(results) == 1
    assert results[0][0] is False
    assert "ffmpeg" in results[0][1].lower()


def test_on_cancel_aborts_running_worker_then_rejects():
    calls: list = []
    worker = SimpleNamespace(isRunning=lambda: True,
                             abort=lambda: calls.append("abort"))
    fake = SimpleNamespace(_worker=worker, reject=lambda: calls.append("reject"))
    GifVideoDialog._on_cancel(fake)
    assert calls == ["abort", "reject"]


def test_on_cancel_without_running_worker_just_rejects():
    calls: list = []
    fake = SimpleNamespace(_worker=None, reject=lambda: calls.append("reject"))
    GifVideoDialog._on_cancel(fake)
    assert calls == ["reject"]


def test_wait_worker_aborts_and_waits_a_running_worker():
    calls: list = []
    worker = SimpleNamespace(isRunning=lambda: True,
                             abort=lambda: calls.append("abort"),
                             wait=lambda: calls.append("wait"))
    GifVideoDialog._wait_worker(SimpleNamespace(_worker=worker))
    assert calls == ["abort", "wait"]


def test_wait_worker_handles_no_worker():
    GifVideoDialog._wait_worker(SimpleNamespace(_worker=None))  # must not raise
