"""The animation dock must stop playback when hidden.

The playback QTimer kept ticking after the dock was closed / the tab switched
away, advancing the timeline and mutating the canvas in the background.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QHideEvent

from Imervue.paint.animation_dock import AnimationDock


def test_stop_playback_stops_the_timer():
    stopped: list = []
    fake = SimpleNamespace(
        _is_playing=True,
        _timer=SimpleNamespace(stop=lambda: stopped.append(True)),
        _play_btn=SimpleNamespace(setText=lambda _t: None),
    )
    AnimationDock.stop_playback(fake)
    assert stopped == [True]
    assert fake._is_playing is False


def test_stop_playback_is_a_noop_when_not_playing():
    stopped: list = []
    fake = SimpleNamespace(
        _is_playing=False,
        _timer=SimpleNamespace(stop=lambda: stopped.append(True)),
    )
    AnimationDock.stop_playback(fake)
    assert stopped == []


def test_hide_event_stops_playback(qapp):
    dock = AnimationDock()
    try:
        dock._is_playing = True
        dock._timer.start(1000)
        assert dock._timer.isActive()
        dock.hideEvent(QHideEvent())
        assert dock.is_playing() is False
        assert not dock._timer.isActive()
    finally:
        dock.deleteLater()
