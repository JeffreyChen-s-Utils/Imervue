"""Tests for the paint menu bar's tooltipsVisible flag — phase 36a.

QMenu hides any per-action tooltips by default; flipping
``setToolTipsVisible(True)`` at construction time means actions that
already have ``setToolTip("Save as PSD (Ctrl+S)")`` actually surface
that hint on hover instead of being readable only via the keystroke
gutter.
"""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_menu_bar import MENU_KEYS, build_paint_menu_bar
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def test_every_top_level_menu_shows_tooltips(qapp):
    """Every menu the bar registers must have toolTipsVisible == True
    so future actions get hover hints without repeating the flag at
    every callsite."""
    ws = PaintWorkspace()
    try:
        bar = build_paint_menu_bar(ws)
        for key, _label in MENU_KEYS:
            menu = bar.findChild(type(bar).__bases__[0], "")  # placeholder
            # Pull the real menu object via the workspace (bar.findChild
            # is unreliable across Qt builds without an objectName).
            menu = getattr(ws, f"_{key}_menu")
            assert menu.toolTipsVisible(), (
                f"{key!r} menu must surface tooltips so action hints render"
            )
    finally:
        ws.deleteLater()
