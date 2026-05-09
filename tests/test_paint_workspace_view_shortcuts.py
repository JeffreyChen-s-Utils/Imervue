"""Tests for the Ctrl+0 / Ctrl+1 view shortcuts — phase 36e.

The shortcut registry has carried ``paint.view.fit`` and
``paint.view.actual_size`` for a while, but nothing in the workspace
actually bound them — only the Edit-menu items did, and only when the
artist had the mouse near the menubar. Wiring QShortcut on the
workspace itself surfaces them globally and makes the existing zoom
indicator tooltip honest about the keystroke it advertises.
"""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def test_fit_view_helper_calls_canvas_reset(qapp):
    ws = PaintWorkspace()
    try:
        called = []
        ws._canvas.reset_view = lambda: called.append("reset")   # noqa: SLF001
        ws._fit_view()   # noqa: SLF001
        assert called == ["reset"]
    finally:
        ws.deleteLater()


def test_actual_size_view_helper_sets_zoom_to_one(qapp):
    ws = PaintWorkspace()
    try:
        captured = []
        ws._canvas.set_zoom = lambda v: captured.append(v)   # noqa: SLF001
        ws._actual_size_view()   # noqa: SLF001
        assert captured == [1.0]
    finally:
        ws.deleteLater()


def test_zoom_indicator_tooltip_includes_shortcut_keys(qapp):
    """The zoom-indicator chip in the status bar advertises the
    fit / actual-size keystrokes pulled from the live registry."""
    ws = PaintWorkspace()
    try:
        tip = ws._zoom_btn.toolTip()   # noqa: SLF001
        assert "Ctrl+0" in tip
        assert "Ctrl+1" in tip
    finally:
        ws.deleteLater()
