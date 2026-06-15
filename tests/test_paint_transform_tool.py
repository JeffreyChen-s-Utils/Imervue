"""Tests for the dispatcher's transform-handle tool."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.tool_dispatcher import ToolDispatcher, _TransformHandleTool
from Imervue.paint.transform_handles import (
    HANDLE_BODY,
    HANDLE_E,
    HANDLE_ROTATE,
    from_rect,
    handle_positions,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def state():
    return ts.load_tool_state()


@pytest.fixture
def canvas():
    return np.full((64, 64, 4), 255, dtype=np.uint8)


class _Workspace:
    """Tiny stand-in for ``PaintWorkspace`` — only exposes the
    duck-typed surface the transform tool uses."""


def _press(x, y):
    return PointerEvent(
        phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0,
    )


def _move(x, y):
    return PointerEvent(
        phase="move", x=x, y=y, button=1, modifiers=0, pressure=1.0,
    )


def _release(x, y):
    return PointerEvent(
        phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0,
    )


# ---------------------------------------------------------------------------
# Pure handler — no Qt
# ---------------------------------------------------------------------------


def test_handler_returns_false_with_no_workspace(state, canvas):
    tool = _TransformHandleTool(state)
    assert tool.handle(_press(10, 10), canvas) is False


def test_handler_seeds_box_to_canvas_extent_on_first_event(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    tool.handle(_press(0, 0), canvas)
    assert hasattr(ws, "_transform_box")
    box = ws._transform_box
    assert box.width == pytest.approx(64.0)
    assert box.height == pytest.approx(64.0)
    assert box.cx == pytest.approx(32.0)
    assert box.cy == pytest.approx(32.0)


def test_press_off_handle_does_not_arm_drag(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    # Click far outside the seeded 64×64 box → no handle, no body.
    handled = tool.handle(_press(500, 500), canvas)
    assert handled is False
    # Subsequent moves must not mutate the box.
    before = ws._transform_box
    tool.handle(_move(510, 510), canvas)
    assert ws._transform_box is before


def test_press_on_body_enables_translation_drag(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    # Click in the centre — that's inside the body, away from any handle.
    handled = tool.handle(_press(32, 32), canvas)
    assert handled is True
    tool.handle(_move(42, 37), canvas)
    box = ws._transform_box
    assert box.cx == pytest.approx(42.0)
    assert box.cy == pytest.approx(37.0)


def test_press_on_e_handle_resizes(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    # Pre-seed the box so we know exactly where the E handle is.
    ws._transform_box = from_rect(0.0, 0.0, 64.0, 64.0)
    e_x, e_y = handle_positions(ws._transform_box)[HANDLE_E]
    handled = tool.handle(_press(e_x, e_y), canvas)
    assert handled is True
    tool.handle(_move(e_x + 10, e_y), canvas)
    box = ws._transform_box
    assert box.width == pytest.approx(74.0)
    assert box.height == pytest.approx(64.0)


def test_press_on_rotate_handle_changes_rotation(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    ws._transform_box = from_rect(0.0, 0.0, 64.0, 64.0)
    rx, ry = handle_positions(ws._transform_box)[HANDLE_ROTATE]
    tool.handle(_press(rx, ry), canvas)
    # Drag the rotate handle horizontally → non-zero rotation.
    tool.handle(_move(rx + 20, ry), canvas)
    assert ws._transform_box.rotation_deg != pytest.approx(0.0)


def test_release_clears_active_handle(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    tool.handle(_press(32, 32), canvas)
    assert tool._active_handle == HANDLE_BODY  # noqa: SLF001
    tool.handle(_release(32, 32), canvas)
    assert tool._active_handle is None  # noqa: SLF001
    # A move after release must not move the box.
    before_cx = ws._transform_box.cx
    tool.handle(_move(99, 99), canvas)
    assert ws._transform_box.cx == pytest.approx(before_cx)


def test_leave_event_also_clears_active_handle(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    tool.handle(_press(32, 32), canvas)
    leave = PointerEvent(
        phase="leave", x=32, y=32, button=0, modifiers=0, pressure=0.0,
    )
    tool.handle(leave, canvas)
    assert tool._active_handle is None  # noqa: SLF001


def test_cancel_clears_state(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    tool.handle(_press(32, 32), canvas)
    tool.cancel()
    assert tool._active_handle is None  # noqa: SLF001
    assert tool._last_pos is None  # noqa: SLF001


def test_move_without_press_is_noop(state, canvas):
    tool = _TransformHandleTool(state)
    ws = _Workspace()
    tool.attach_workspace(ws)
    handled = tool.handle(_move(10, 10), canvas)
    assert handled is False


# ---------------------------------------------------------------------------
# Dispatcher routing — transform tool registered + bypasses Alt-eyedropper
# ---------------------------------------------------------------------------


def test_dispatcher_registers_transform_tool(state, canvas):
    disp = ToolDispatcher(state, image_provider=lambda: canvas)
    assert "transform" in disp._handlers  # noqa: SLF001
    assert isinstance(
        disp._handlers["transform"],  # noqa: SLF001
        _TransformHandleTool,
    )


def test_dispatcher_routes_to_transform_when_active(state, canvas):
    disp = ToolDispatcher(state, image_provider=lambda: canvas)
    state.set_tool("transform")
    transform_tool = disp._handlers["transform"]  # noqa: SLF001
    transform_tool.attach_workspace(_Workspace())
    # Press at body centre → handler returns True.
    assert disp(_press(32, 32)) is True


# ---------------------------------------------------------------------------
# Workspace wiring — attach_workspace fires
# ---------------------------------------------------------------------------


def test_workspace_attaches_transform_tool(qapp):
    ws = PaintWorkspace()
    try:
        transform_tool = ws._dispatcher._handlers["transform"]  # noqa: SLF001
        assert transform_tool._workspace is ws  # noqa: SLF001
    finally:
        ws.deleteLater()
