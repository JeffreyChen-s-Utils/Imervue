"""The video-import dialog must release its ffmpeg reader (and worker) on close.

The dialog is parented to the viewer so it isn't GC'd, and FrameReader has no
__del__, so without an explicit close each open leaked an ffmpeg subprocess.
Driven on the extracted _release helper with fakes -- no Qt dialog constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from video_source.video_source_plugin import VideoImportDialog


def test_release_closes_the_reader():
    closed: list = []
    fake = SimpleNamespace(
        _reader=SimpleNamespace(close=lambda: closed.append(True)), _worker=None)
    VideoImportDialog._release(fake)
    assert closed == [True]


def test_release_waits_the_worker_then_closes_the_reader():
    order: list = []
    fake = SimpleNamespace(
        _worker=SimpleNamespace(
            isRunning=lambda: True, wait=lambda: order.append("wait")),
        _reader=SimpleNamespace(close=lambda: order.append("close")),
    )
    VideoImportDialog._release(fake)
    assert order == ["wait", "close"]


def test_release_is_safe_when_reader_close_raises():
    def boom():
        raise RuntimeError("ffmpeg already gone")

    fake = SimpleNamespace(_reader=SimpleNamespace(close=boom), _worker=None)
    VideoImportDialog._release(fake)   # suppressed, must not raise
