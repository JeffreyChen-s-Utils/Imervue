"""Tests for move tool + selection clipping of brush / fill / eraser."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.brush_engine import (
    BrushStroke,
    BrushStrokeOptions,
    apply_dab,
    apply_erase_dab,
    round_brush_kernel,
)
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.fill import flood_fill
from Imervue.paint.tool_dispatcher import (
    BrushTool,
    EraserTool,
    FillTool,
    MoveTool,
    ToolDispatcher,
    translate_selection,
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
    return ts.load_tool_state()


def _press(x, y):
    return PointerEvent(phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0)


def _release(x, y):
    return PointerEvent(phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0)


# ---------------------------------------------------------------------------
# apply_dab with selection
# ---------------------------------------------------------------------------


def test_apply_dab_paints_only_inside_selection():
    canvas = np.zeros((20, 20, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    k = round_brush_kernel(7, hardness=1.0)
    apply_dab(canvas, 10, 10, k, (255, 0, 0), selection=sel)
    # Inside the selection: red painted.
    assert canvas[10, 10, 0] == 255
    # Outside the selection: untouched.
    assert canvas[3, 10, 0] == 0


def test_apply_dab_rejects_wrong_selection_shape():
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    bad_sel = np.zeros((5, 5), dtype=np.bool_)
    k = round_brush_kernel(3, hardness=1.0)
    with pytest.raises(ValueError):
        apply_dab(canvas, 5, 5, k, (255, 0, 0), selection=bad_sel)


def test_apply_erase_dab_with_selection_clamps_alpha_drop():
    canvas = np.full((20, 20, 4), 255, dtype=np.uint8)
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    k = round_brush_kernel(7, hardness=1.0)
    apply_erase_dab(canvas, 10, 10, k, selection=sel)
    # Inside selection: alpha dropped.
    assert canvas[10, 10, 3] == 0
    # Outside selection: alpha preserved.
    assert canvas[3, 10, 3] == 255


# ---------------------------------------------------------------------------
# BrushStroke with selection
# ---------------------------------------------------------------------------


def test_brush_stroke_clipped_by_selection():
    canvas = np.zeros((20, 20, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=3, opacity=1.0, hardness=1.0, selection=sel,
    ))
    stroke.begin(canvas, 0, 10)   # start outside the selection
    stroke.extend(canvas, 19, 10)  # exit on the other side
    stroke.end(canvas, 19, 10)
    # Only inside the selection has red pixels.
    assert canvas[10, 10, 0] == 255
    assert canvas[10, 0, 0] == 0    # outside left
    assert canvas[10, 19, 0] == 0   # outside right


# ---------------------------------------------------------------------------
# flood_fill with selection
# ---------------------------------------------------------------------------


def test_flood_fill_clipped_by_selection():
    canvas = np.full((20, 20, 4), 255, dtype=np.uint8)
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    out = flood_fill(canvas, 10, 10, (200, 0, 0), tolerance=0, selection=sel)
    # Filled exactly the selection's 10×10 block (because the whole sel is white).
    assert out.pixels_filled == 100


def test_flood_fill_seed_outside_selection_is_noop():
    canvas = np.full((20, 20, 4), 255, dtype=np.uint8)
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    out = flood_fill(canvas, 0, 0, (200, 0, 0), tolerance=0, selection=sel)
    assert out.is_empty


def test_flood_fill_rejects_selection_shape_mismatch():
    canvas = np.full((10, 10, 4), 255, dtype=np.uint8)
    bad_sel = np.zeros((5, 5), dtype=np.bool_)
    with pytest.raises(ValueError):
        flood_fill(canvas, 5, 5, (200, 0, 0), selection=bad_sel)


# ---------------------------------------------------------------------------
# translate_selection
# ---------------------------------------------------------------------------


def test_translate_selection_moves_pixels():
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    canvas[3, 3] = (255, 0, 0, 255)
    sel = np.zeros((10, 10), dtype=np.bool_)
    sel[3, 3] = True
    new_sel = translate_selection(canvas, sel, dx=2, dy=1)
    # Pixel was cut from (3,3) and pasted at (5, 4).
    assert tuple(canvas[3, 3]) == (0, 0, 0, 0)
    assert tuple(canvas[4, 5]) == (255, 0, 0, 255)
    assert new_sel[4, 5]
    assert not new_sel[3, 3]


def test_translate_selection_drops_off_canvas_pixels():
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    canvas[3, 3] = (255, 0, 0, 255)
    sel = np.zeros((10, 10), dtype=np.bool_)
    sel[3, 3] = True
    new_sel = translate_selection(canvas, sel, dx=20, dy=20)
    assert tuple(canvas[3, 3]) == (0, 0, 0, 0)
    assert new_sel.sum() == 0


def test_translate_selection_zero_delta_is_noop():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[2, 2] = (1, 2, 3, 255)
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[2, 2] = True
    new_sel = translate_selection(canvas, sel, dx=0, dy=0)
    assert tuple(canvas[2, 2]) == (1, 2, 3, 255)
    assert new_sel[2, 2]


def test_translate_selection_rejects_shape_mismatch():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    bad_sel = np.zeros((3, 3), dtype=np.bool_)
    with pytest.raises(ValueError):
        translate_selection(canvas, bad_sel, dx=1, dy=1)


def test_translate_selection_rejects_non_rgba():
    canvas = np.zeros((4, 4, 3), dtype=np.uint8)
    sel = np.zeros((4, 4), dtype=np.bool_)
    with pytest.raises(ValueError):
        translate_selection(canvas, sel, dx=0, dy=0)


# ---------------------------------------------------------------------------
# MoveTool dispatcher
# ---------------------------------------------------------------------------


def test_move_tool_translates_selection_on_release(state):
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    canvas[3, 3] = (255, 0, 0, 255)
    sel = np.zeros((10, 10), dtype=np.bool_)
    sel[3, 3] = True

    holder: list = [sel]
    tool = MoveTool(state, lambda: holder[0], lambda m: holder.__setitem__(0, m))
    tool.handle(_press(3, 3), canvas)
    tool.handle(_release(5, 5), canvas)
    assert tuple(canvas[5, 5]) == (255, 0, 0, 255)
    assert holder[0][5, 5]


def test_move_tool_zero_drag_is_noop(state):
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    canvas[3, 3] = (255, 0, 0, 255)
    sel = np.zeros((10, 10), dtype=np.bool_)
    sel[3, 3] = True
    holder: list = [sel]
    tool = MoveTool(state, lambda: holder[0], lambda m: holder.__setitem__(0, m))
    tool.handle(_press(3, 3), canvas)
    assert tool.handle(_release(3, 3), canvas) is False
    assert tuple(canvas[3, 3]) == (255, 0, 0, 255)


def test_move_tool_without_selection_moves_whole_canvas(state):
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    canvas[5, 5] = (1, 2, 3, 255)
    holder: list = [None]
    tool = MoveTool(state, lambda: holder[0], lambda m: holder.__setitem__(0, m))
    tool.handle(_press(0, 0), canvas)
    tool.handle(_release(2, 2), canvas)
    assert tuple(canvas[7, 7]) == (1, 2, 3, 255)


def test_move_tool_release_without_press_returns_false(state):
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    tool = MoveTool(state, lambda: None, lambda m: None)
    assert tool.handle(_release(2, 2), canvas) is False


# ---------------------------------------------------------------------------
# Dispatcher integration — selection clipping flows through the brush
# ---------------------------------------------------------------------------


def test_dispatcher_brush_respects_selection(state):
    canvas = np.zeros((20, 20, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    state.set_foreground((255, 0, 0))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)

    disp = ToolDispatcher(
        state,
        image_provider=lambda: canvas,
        selection_provider=lambda: sel,
        set_selection=lambda m: None,
    )
    disp(_press(0, 10))     # outside the selection
    disp(_release(0, 10))
    assert canvas[10, 0, 0] == 0   # never painted

    disp(_press(10, 10))    # inside
    disp(_release(10, 10))
    assert canvas[10, 10, 0] == 255


def test_dispatcher_routes_move_tool(state):
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    canvas[3, 3] = (255, 0, 0, 255)
    sel = np.zeros((10, 10), dtype=np.bool_)
    sel[3, 3] = True
    holder: list = [sel]

    state.set_tool("move")
    disp = ToolDispatcher(
        state,
        image_provider=lambda: canvas,
        selection_provider=lambda: holder[0],
        set_selection=lambda m: holder.__setitem__(0, m),
    )
    disp(_press(3, 3))
    assert disp(_release(5, 4)) is True
    assert tuple(canvas[4, 5]) == (255, 0, 0, 255)


# ---------------------------------------------------------------------------
# Existing tools still work without a selection
# ---------------------------------------------------------------------------


def test_brush_without_selection_paints_everywhere(state):
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    state.set_foreground((255, 0, 0))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    tool = BrushTool(state)  # default no selection_provider
    tool.handle(_press(5, 5), canvas)
    assert canvas[5, 5, 0] == 255


def test_eraser_without_selection_erases_everywhere(state):
    canvas = np.full((10, 10, 4), 255, dtype=np.uint8)
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    tool = EraserTool(state)
    tool.handle(_press(5, 5), canvas)
    assert canvas[5, 5, 3] == 0


def test_fill_without_selection_floods_full_region(state):
    canvas = np.full((10, 10, 4), 255, dtype=np.uint8)
    state.set_foreground((255, 0, 0))
    tool = FillTool(state)
    tool.handle(_press(5, 5), canvas)
    assert canvas[0, 0, 0] == 255  # entire white area filled red
