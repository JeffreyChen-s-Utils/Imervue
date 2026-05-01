"""Tests for the Tools menu + the new pen / clone-stamp tools."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.paint_menu_bar import menu_for
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.tools_menu import TOOL_ENTRIES, _ToolsMenuBridge
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# TOOLS catalogue
# ---------------------------------------------------------------------------


def test_tools_catalogue_includes_new_pen_and_stamp():
    assert "bezier_pen" in ts.TOOLS
    assert "clone_stamp" in ts.TOOLS


def test_tool_entries_unique_tool_ids():
    ids = [entry.tool_id for entry in TOOL_ENTRIES]
    assert len(ids) == len(set(ids))


def test_tool_entries_unique_shortcuts():
    shortcuts = [entry.shortcut for entry in TOOL_ENTRIES]
    assert len(shortcuts) == len(set(shortcuts))


# ---------------------------------------------------------------------------
# Menu population
# ---------------------------------------------------------------------------


def test_tools_menu_lists_documented_actions(qapp):
    ws = PaintWorkspace()
    try:
        tools_menu = menu_for(ws, "tools")
        assert len(tools_menu.actions()) == len(TOOL_ENTRIES)
    finally:
        ws.deleteLater()


def test_tools_menu_actions_have_translated_labels(qapp):
    ws = PaintWorkspace()
    try:
        tools_menu = menu_for(ws, "tools")
        labels = [a.text() for a in tools_menu.actions()]
        for label in labels:
            assert not label.startswith("paint_tool_"), label
    finally:
        ws.deleteLater()


def test_tools_menu_actions_have_shortcuts(qapp):
    ws = PaintWorkspace()
    try:
        tools_menu = menu_for(ws, "tools")
        for action in tools_menu.actions():
            assert not action.shortcut().isEmpty(), action.text()
    finally:
        ws.deleteLater()


def test_tools_menu_actions_are_checkable(qapp):
    """Every entry is a single-select toggle so the menu shows
    which tool is currently active."""
    ws = PaintWorkspace()
    try:
        tools_menu = menu_for(ws, "tools")
        for action in tools_menu.actions():
            assert action.isCheckable(), action.text()
    finally:
        ws.deleteLater()


def test_workspace_holds_bridge_reference(qapp):
    ws = PaintWorkspace()
    try:
        assert isinstance(ws._tools_menu_bridge, _ToolsMenuBridge)  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------


def test_activate_writes_tool_state(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._tools_menu_bridge   # noqa: SLF001
        bridge.activate("eraser")
        assert ws.state().tool == "eraser"
    finally:
        ws.deleteLater()


def test_check_state_follows_active_tool(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._tools_menu_bridge   # noqa: SLF001
        bridge.activate("eraser")
        assert bridge._actions["eraser"].isChecked()  # noqa: SLF001
        for tool_id, action in bridge._actions.items():  # noqa: SLF001
            if tool_id == "eraser":
                assert action.isChecked()
            else:
                assert not action.isChecked()
    finally:
        ws.deleteLater()


def test_check_state_updates_when_state_changes_externally(qapp):
    """The bridge subscribes to ToolState changes so a shortcut /
    toolbar pick of a tool also updates the menu's check mark."""
    ws = PaintWorkspace()
    try:
        bridge = ws._tools_menu_bridge   # noqa: SLF001
        # Change tool via the state (simulating toolbar click).
        ws.state().set_tool("smudge")
        assert bridge._actions["smudge"].isChecked()  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Bezier pen tool
# ---------------------------------------------------------------------------


def test_pen_tool_press_appends_anchor(qapp):
    ws = PaintWorkspace()
    try:
        ws.state().set_tool("bezier_pen")
        canvas = np.zeros((40, 40, 4), dtype=np.uint8)
        ws._dispatcher._image_provider = lambda: canvas   # noqa: SLF001
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="press", x=10.0, y=10.0,
            button=1, modifiers=0, pressure=1.0,
        ))
        path = ws._bezier_pen_path   # noqa: SLF001
        assert len(path.nodes) == 1
        assert path.nodes[0].anchor == (10.0, 10.0)
    finally:
        ws.deleteLater()


def test_pen_tool_drag_extends_out_handle(qapp):
    ws = PaintWorkspace()
    try:
        ws.state().set_tool("bezier_pen")
        canvas = np.zeros((40, 40, 4), dtype=np.uint8)
        ws._dispatcher._image_provider = lambda: canvas   # noqa: SLF001
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="press", x=10.0, y=10.0,
            button=1, modifiers=0, pressure=1.0,
        ))
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="move", x=15.0, y=12.0,
            button=1, modifiers=0, pressure=1.0,
        ))
        path = ws._bezier_pen_path   # noqa: SLF001
        assert path.nodes[0].handle_out == (15.0, 12.0)
    finally:
        ws.deleteLater()


def test_pen_tool_release_clears_drag_state(qapp):
    """After release a fresh press starts a new anchor (rather than
    continuing to extend the previous one's handle)."""
    ws = PaintWorkspace()
    try:
        ws.state().set_tool("bezier_pen")
        canvas = np.zeros((40, 40, 4), dtype=np.uint8)
        ws._dispatcher._image_provider = lambda: canvas   # noqa: SLF001
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="press", x=10.0, y=10.0,
            button=1, modifiers=0, pressure=1.0,
        ))
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="release", x=10.0, y=10.0,
            button=0, modifiers=0, pressure=1.0,
        ))
        # Subsequent move alone (no press) must NOT update anchor[0].
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="move", x=99.0, y=99.0,
            button=0, modifiers=0, pressure=1.0,
        ))
        path = ws._bezier_pen_path   # noqa: SLF001
        assert path.nodes[0].handle_out is None
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Clone-stamp tool
# ---------------------------------------------------------------------------


_ALT = 0x08000000


def test_clone_stamp_alt_press_sets_source(qapp):
    ws = PaintWorkspace()
    try:
        ws.state().set_tool("clone_stamp")
        canvas = np.full((40, 40, 4), 255, dtype=np.uint8)
        ws._dispatcher._image_provider = lambda: canvas   # noqa: SLF001
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="press", x=10.0, y=10.0,
            button=1, modifiers=_ALT, pressure=1.0,
        ))
        stamp_tool = ws._dispatcher._handlers["clone_stamp"]   # noqa: SLF001
        assert stamp_tool._stamp.has_source()  # noqa: SLF001
        assert stamp_tool._stamp.source == (10.0, 10.0)  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_clone_stamp_press_without_source_is_no_op(qapp):
    ws = PaintWorkspace()
    try:
        ws.state().set_tool("clone_stamp")
        canvas = np.full((40, 40, 4), 255, dtype=np.uint8)
        snapshot = canvas.copy()
        ws._dispatcher._image_provider = lambda: canvas   # noqa: SLF001
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="press", x=20.0, y=20.0,
            button=1, modifiers=0, pressure=1.0,
        ))
        np.testing.assert_array_equal(canvas, snapshot)
    finally:
        ws.deleteLater()


def test_clone_stamp_paints_after_source_is_set(qapp):
    ws = PaintWorkspace()
    try:
        ws.state().set_tool("clone_stamp")
        ws.state().set_brush(size=8, hardness=1.0, opacity=1.0)
        canvas = np.full((40, 40, 4), 255, dtype=np.uint8)
        canvas[5:15, 5:15] = (200, 0, 0, 255)   # source area
        ws._dispatcher._image_provider = lambda: canvas   # noqa: SLF001
        # Alt-press → set source.
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="press", x=10.0, y=10.0,
            button=1, modifiers=_ALT, pressure=1.0,
        ))
        # Plain press → stamp at the destination.
        ws._dispatcher(PointerEvent(  # noqa: SLF001
            phase="press", x=30.0, y=30.0,
            button=1, modifiers=0, pressure=1.0,
        ))
        # Centre of the destination region should now be tinted red.
        assert int(canvas[30, 30, 0]) >= 100
        assert int(canvas[30, 30, 2]) <= 200
    finally:
        ws.deleteLater()
