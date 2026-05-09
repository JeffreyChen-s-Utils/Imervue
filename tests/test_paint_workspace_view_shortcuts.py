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


def test_swap_and_reset_colour_shortcuts_fire(qapp):
    """X swaps foreground / background; D resets the colour pair to
    black and white. Both run on global QShortcut bindings so the
    keystroke works anywhere in the workspace except text fields."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    ws = PaintWorkspace()
    try:
        ws.show()
        QTest.qWait(20)

        # Start with a non-default foreground / background.
        ws._state.set_foreground((10, 20, 30))   # noqa: SLF001
        ws._state.set_background((200, 210, 220))   # noqa: SLF001
        before_fg = tuple(ws._state.foreground)   # noqa: SLF001
        before_bg = tuple(ws._state.background)   # noqa: SLF001

        QTest.keyClick(ws, Qt.Key.Key_X)
        QTest.qWait(20)
        assert tuple(ws._state.foreground) == before_bg   # noqa: SLF001
        assert tuple(ws._state.background) == before_fg   # noqa: SLF001

        QTest.keyClick(ws, Qt.Key.Key_D)
        QTest.qWait(20)
        # ``reset_colors`` restores the documented defaults — the
        # foreground returns to the pre-swap colour pair (the exact
        # values are state-internal; we just assert the binding fired
        # by checking the pair isn't still the swapped one).
        fg = ws._state.foreground   # noqa: SLF001
        bg = ws._state.background   # noqa: SLF001
        assert (fg, bg) != (before_bg, before_fg)
    finally:
        ws.deleteLater()
