"""The deferred pixel-grid signal hookup must survive a torn-down canvas.

connect_canvas_signals runs from a QTimer.singleShot; if the workspace was closed
before it fired, canvas.zoom_changed.connect raised 'Signal source has been
deleted'. It is now guarded. Driven on the bridge method unbound with fakes.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.paint.view_menu import _ViewMenuBridge


def _bridge(canvas, refreshed):
    return SimpleNamespace(
        _workspace=SimpleNamespace(_canvas=canvas),
        refresh_pixel_grid_label=lambda: refreshed.append(True),
    )


def test_connect_survives_a_deleted_canvas():
    def boom(_cb):
        raise RuntimeError("Signal source has been deleted")

    refreshed: list = []
    canvas = SimpleNamespace(zoom_changed=SimpleNamespace(connect=boom))
    _ViewMenuBridge.connect_canvas_signals(_bridge(canvas, refreshed))  # no raise
    assert refreshed == []   # connect failed -> the trailing refresh is skipped


def test_connect_wires_a_live_canvas():
    connected: list = []
    refreshed: list = []
    canvas = SimpleNamespace(
        zoom_changed=SimpleNamespace(connect=connected.append))
    _ViewMenuBridge.connect_canvas_signals(_bridge(canvas, refreshed))
    assert len(connected) == 1
    assert refreshed == [True]


def test_connect_is_a_noop_without_a_canvas():
    _ViewMenuBridge.connect_canvas_signals(
        SimpleNamespace(_workspace=SimpleNamespace(_canvas=None)))   # no raise
