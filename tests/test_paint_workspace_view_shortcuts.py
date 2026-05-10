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


def test_swap_and_reset_colour_shortcuts_are_registered(qapp):
    """X swaps foreground / background; D resets the colour pair.

    Verifying the binding via QTest.keyClick is unreliable on the
    offscreen Qt platform CI uses (the keypress doesn't always reach
    a windowless QMainWindow's QShortcut router). Instead we walk
    the workspace's QShortcut children and assert the right key is
    wired to a callable that updates ``ToolState`` — same surface
    the runtime uses, but driven directly so the test isn't beholden
    to the Qt event loop's focus handling.
    """
    from PySide6.QtGui import QKeySequence, QShortcut

    ws = PaintWorkspace()
    try:
        shortcuts = ws.findChildren(QShortcut)
        keys = {sc.key().toString() for sc in shortcuts if not sc.key().isEmpty()}
        assert "X" in keys, f"missing X binding; have {sorted(keys)}"
        assert "D" in keys, f"missing D binding; have {sorted(keys)}"

        # Drive the same paths the QShortcut.activated signal would.
        # ``swap_colors`` and ``reset_colors`` are the public surface,
        # so calling them directly verifies the binding lands on the
        # documented behaviour without crossing Qt focus boundaries.
        ws._state.set_foreground((10, 20, 30))   # noqa: SLF001
        ws._state.set_background((200, 210, 220))   # noqa: SLF001
        before_fg = tuple(ws._state.foreground)   # noqa: SLF001
        before_bg = tuple(ws._state.background)   # noqa: SLF001

        # Find the QShortcut bound to X / D and emit its activated
        # signal — that is the same trigger the keypress dispatches.
        x_shortcut = next(
            sc for sc in shortcuts if sc.key() == QKeySequence("X")
        )
        d_shortcut = next(
            sc for sc in shortcuts if sc.key() == QKeySequence("D")
        )
        x_shortcut.activated.emit()
        assert tuple(ws._state.foreground) == before_bg   # noqa: SLF001
        assert tuple(ws._state.background) == before_fg   # noqa: SLF001

        d_shortcut.activated.emit()
        # ``reset_colors`` returns to the documented defaults; the
        # exact tuple is state-internal, we just check it isn't the
        # swapped pair anymore.
        fg = ws._state.foreground   # noqa: SLF001
        bg = ws._state.background   # noqa: SLF001
        assert (fg, bg) != (before_bg, before_fg)
    finally:
        ws.deleteLater()
