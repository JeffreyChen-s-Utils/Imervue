"""Tests for the shape-tool dispatcher classes."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.tool_dispatcher import (
    ToolDispatcher,
    _EllipseShapeTool,
    _LineShapeTool,
    _PolygonShapeTool,
    _RectShapeTool,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def state():
    s = ts.load_tool_state()
    s.set_foreground((255, 0, 0))
    s.set_brush(size=2)
    return s


@pytest.fixture
def canvas():
    return np.zeros((48, 48, 4), dtype=np.uint8)


def _press(x, y, button: int = 1):
    return PointerEvent(
        phase="press", x=x, y=y, button=button, modifiers=0, pressure=1.0,
    )


def _release(x, y):
    return PointerEvent(
        phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0,
    )


# ---------------------------------------------------------------------------
# Dispatcher registration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name,cls", [
    ("shape_rect", _RectShapeTool),
    ("shape_ellipse", _EllipseShapeTool),
    ("shape_line", _LineShapeTool),
    ("shape_polygon", _PolygonShapeTool),
])
def test_dispatcher_registers_shape_tool(state, canvas, tool_name, cls):
    disp = ToolDispatcher(state, image_provider=lambda: canvas)
    assert tool_name in disp._handlers  # noqa: SLF001
    assert isinstance(disp._handlers[tool_name], cls)  # noqa: SLF001


# ---------------------------------------------------------------------------
# Rect / ellipse / line — drag-to-define
# ---------------------------------------------------------------------------


def test_rect_press_release_paints(state, canvas):
    tool = _RectShapeTool(state)
    tool.handle(_press(8, 8), canvas)
    handled = tool.handle(_release(32, 24), canvas)
    assert handled is True
    assert tuple(canvas[16, 20]) == (255, 0, 0, 255)


def test_rect_release_without_press_is_noop(state, canvas):
    tool = _RectShapeTool(state)
    handled = tool.handle(_release(20, 20), canvas)
    assert handled is False


def test_rect_zero_drag_is_noop(state, canvas):
    tool = _RectShapeTool(state)
    tool.handle(_press(20, 20), canvas)
    handled = tool.handle(_release(20, 20), canvas)
    assert handled is False
    assert canvas.sum() == 0


def test_ellipse_press_release_paints(state, canvas):
    tool = _EllipseShapeTool(state)
    tool.handle(_press(8, 8), canvas)
    handled = tool.handle(_release(40, 40), canvas)
    assert handled is True
    # Centre of bounding box (24, 24) is inside the ellipse.
    assert tuple(canvas[24, 24]) == (255, 0, 0, 255)


def test_line_press_release_paints(state, canvas):
    tool = _LineShapeTool(state)
    tool.handle(_press(8, 8), canvas)
    handled = tool.handle(_release(40, 40), canvas)
    assert handled is True
    # Endpoints visible.
    assert (canvas[8, 8] != 0).any()
    assert (canvas[40, 40] != 0).any()


def test_line_click_only_paints_dot(state, canvas):
    """A press+release at the same point should still leave a visible
    dab — matches the brush convention."""
    tool = _LineShapeTool(state)
    tool.handle(_press(20, 20), canvas)
    handled = tool.handle(_release(20, 20), canvas)
    assert handled is True
    assert (canvas[20, 20] != 0).any()


# ---------------------------------------------------------------------------
# Polygon — multi-click + close gestures
# ---------------------------------------------------------------------------


def test_polygon_collects_vertices_silently(state, canvas):
    tool = _PolygonShapeTool(state)
    # Three press events, none close the loop → no rasterisation.
    for x, y in [(10, 10), (40, 10), (25, 35)]:
        handled = tool.handle(_press(x, y), canvas)
        assert handled is False
    assert canvas.sum() == 0
    assert len(tool._vertices) == 3  # noqa: SLF001


def test_polygon_close_via_click_near_first_vertex(state, canvas):
    tool = _PolygonShapeTool(state)
    tool.handle(_press(10, 10), canvas)
    tool.handle(_press(40, 10), canvas)
    tool.handle(_press(25, 35), canvas)
    # Click within CLOSE_RADIUS of (10, 10) closes the polygon.
    handled = tool.handle(_press(11, 11), canvas)
    assert handled is True
    # Triangle is now filled — the centroid is opaque.
    assert tuple(canvas[18, 25]) == (255, 0, 0, 255)
    # Vertex list reset for the next polygon.
    assert tool._vertices == []  # noqa: SLF001


def test_polygon_close_via_right_click(state, canvas):
    tool = _PolygonShapeTool(state)
    tool.handle(_press(10, 10), canvas)
    tool.handle(_press(40, 10), canvas)
    tool.handle(_press(25, 35), canvas)
    handled = tool.handle(_press(20, 20, button=2), canvas)
    assert handled is True
    assert tool._vertices == []  # noqa: SLF001


def test_polygon_right_click_with_no_vertices_is_noop(state, canvas):
    tool = _PolygonShapeTool(state)
    handled = tool.handle(_press(10, 10, button=2), canvas)
    assert handled is False
    # Stray right-click adds a vertex (left-click semantics)? No —
    # with empty list the right-click branch falls through to the
    # vertex-append branch since "self._vertices" was empty.
    # Verify behaviour is stable.
    assert isinstance(tool._vertices, list)  # noqa: SLF001


# ---------------------------------------------------------------------------
# Cancel + leave hygiene
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_cls", [
    _RectShapeTool, _EllipseShapeTool, _LineShapeTool,
])
def test_drag_tool_cancel_clears_press_state(state, canvas, tool_cls):
    tool = tool_cls(state)
    tool.handle(_press(10, 10), canvas)
    tool.cancel()
    handled = tool.handle(_release(40, 40), canvas)
    assert handled is False


def test_polygon_cancel_clears_vertices(state, canvas):
    tool = _PolygonShapeTool(state)
    tool.handle(_press(10, 10), canvas)
    tool.handle(_press(40, 10), canvas)
    tool.cancel()
    assert tool._vertices == []  # noqa: SLF001


@pytest.mark.parametrize("tool_cls", [
    _RectShapeTool, _EllipseShapeTool, _LineShapeTool,
])
def test_drag_tool_leave_clears_press(state, canvas, tool_cls):
    tool = tool_cls(state)
    tool.handle(_press(10, 10), canvas)
    leave = PointerEvent(
        phase="leave", x=10, y=10, button=0, modifiers=0, pressure=0.0,
    )
    tool.handle(leave, canvas)
    handled = tool.handle(_release(40, 40), canvas)
    assert handled is False


# ---------------------------------------------------------------------------
# All four tools registered in TOOLS catalogue
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", [
    "shape_rect", "shape_ellipse", "shape_line", "shape_polygon",
])
def test_shape_tool_in_catalogue(name):
    assert name in ts.TOOLS
