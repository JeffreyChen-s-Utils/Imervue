"""_connect_screen_change_signal must retry until windowHandle() exists.

windowHandle() is None on the first deferred attempt (before the native window
is shown); a one-shot that gave up then left the screenChanged signal
permanently unconnected, so dragging/restoring the window to another monitor
never re-fit the view. Driven on the unbound method with a fake self.
"""
from __future__ import annotations

from types import SimpleNamespace

import Imervue.Imervue_main_window as mw
from Imervue.Imervue_main_window import ImervueMainWindow


class _FakeTimer:
    calls: list = []

    @staticmethod
    def singleShot(ms, fn):   # noqa: N802 - mirrors Qt's API
        _FakeTimer.calls.append((ms, fn))


def test_retries_when_window_handle_missing(monkeypatch):
    monkeypatch.setattr(mw, "QTimer", _FakeTimer)
    _FakeTimer.calls = []
    fake = SimpleNamespace(_screen_signal_connected=False, windowHandle=lambda: None)

    ImervueMainWindow._connect_screen_change_signal(fake, _retries=3)

    assert len(_FakeTimer.calls) == 1     # scheduled a retry
    assert _FakeTimer.calls[0][0] == 50   # ...on a 50ms timer
    assert fake._screen_signal_connected is False


def test_gives_up_after_retries_exhausted(monkeypatch):
    monkeypatch.setattr(mw, "QTimer", _FakeTimer)
    _FakeTimer.calls = []
    fake = SimpleNamespace(_screen_signal_connected=False, windowHandle=lambda: None)

    ImervueMainWindow._connect_screen_change_signal(fake, _retries=0)

    assert _FakeTimer.calls == []         # no infinite retry loop
    assert fake._screen_signal_connected is False


def test_connects_when_handle_ready(monkeypatch):
    monkeypatch.setattr(mw, "QTimer", _FakeTimer)
    _FakeTimer.calls = []
    connected: list = []
    handle = SimpleNamespace(
        screenChanged=SimpleNamespace(connect=lambda slot: connected.append(slot)))
    fake = SimpleNamespace(
        _screen_signal_connected=False,
        windowHandle=lambda: handle,
        _on_screen_changed=lambda _s: None,
    )

    ImervueMainWindow._connect_screen_change_signal(fake)

    assert len(connected) == 1            # signal wired
    assert fake._screen_signal_connected is True
    assert _FakeTimer.calls == []         # connected directly, no retry


def test_noop_when_already_connected(monkeypatch):
    monkeypatch.setattr(mw, "QTimer", _FakeTimer)
    _FakeTimer.calls = []
    fake = SimpleNamespace(_screen_signal_connected=True, windowHandle=lambda: None)

    ImervueMainWindow._connect_screen_change_signal(fake)

    assert _FakeTimer.calls == []         # already connected, nothing to do
