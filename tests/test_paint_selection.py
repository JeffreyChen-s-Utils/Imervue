"""Tests for the selection mask helpers and the three selection tools."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.selection import (
    SELECTION_MODES,
    combine,
    magic_wand_mask,
    polygon_mask,
    rectangle_mask,
)
from Imervue.paint.tool_dispatcher import (
    LassoSelectTool,
    QuickSelectTool,
    RectSelectTool,
    WandSelectTool,
    _SelectionContext,
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


@pytest.fixture
def canvas():
    arr = np.full((16, 16, 4), 255, dtype=np.uint8)
    arr[4:12, 4:12, :3] = 0
    return arr


# ---------------------------------------------------------------------------
# combine() modes
# ---------------------------------------------------------------------------


def test_combine_replace_with_no_existing():
    new = np.array([[True, False], [True, True]])
    np.testing.assert_array_equal(combine(None, new, "replace"), new)


def test_combine_add_with_no_existing():
    new = np.array([[True, False], [True, True]])
    np.testing.assert_array_equal(combine(None, new, "add"), new)


def test_combine_subtract_with_no_existing_yields_empty():
    new = np.array([[True, False], [True, True]])
    out = combine(None, new, "subtract")
    assert out.any() is np.False_ or out.sum() == 0


def test_combine_intersect_with_no_existing_yields_empty():
    new = np.array([[True, False], [True, True]])
    out = combine(None, new, "intersect")
    assert out.sum() == 0


def test_combine_replace_overwrites():
    a = np.array([[True, True], [False, False]])
    b = np.array([[False, True], [True, False]])
    np.testing.assert_array_equal(combine(a, b, "replace"), b)


def test_combine_add_unions():
    a = np.array([[True, False], [False, False]])
    b = np.array([[False, True], [False, False]])
    np.testing.assert_array_equal(
        combine(a, b, "add"),
        np.array([[True, True], [False, False]]),
    )


def test_combine_subtract_clears_overlap():
    a = np.array([[True, True], [False, False]])
    b = np.array([[True, False], [False, False]])
    np.testing.assert_array_equal(
        combine(a, b, "subtract"),
        np.array([[False, True], [False, False]]),
    )


def test_combine_intersect_keeps_overlap():
    a = np.array([[True, True], [False, False]])
    b = np.array([[True, False], [False, True]])
    np.testing.assert_array_equal(
        combine(a, b, "intersect"),
        np.array([[True, False], [False, False]]),
    )


def test_combine_rejects_unknown_mode():
    a = np.zeros((2, 2), dtype=np.bool_)
    with pytest.raises(ValueError):
        combine(a, a, "vivid")


def test_combine_rejects_non_bool_new():
    a = np.zeros((2, 2), dtype=np.bool_)
    bad = np.zeros((2, 2), dtype=np.uint8)
    with pytest.raises(ValueError):
        combine(a, bad, "replace")


def test_combine_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        combine(np.zeros((2, 2), bool), np.zeros((3, 3), bool), "add")


def test_selection_modes_listed():
    assert SELECTION_MODES == ("replace", "add", "subtract", "intersect")


# ---------------------------------------------------------------------------
# rectangle_mask
# ---------------------------------------------------------------------------


def test_rectangle_mask_basic():
    mask = rectangle_mask(4, 4, 1, 1, 2, 2)
    expected = np.array([
        [False, False, False, False],
        [False, True,  True,  False],
        [False, True,  True,  False],
        [False, False, False, False],
    ])
    np.testing.assert_array_equal(mask, expected)


def test_rectangle_mask_swaps_endpoints():
    a = rectangle_mask(4, 4, 0, 0, 2, 2)
    b = rectangle_mask(4, 4, 2, 2, 0, 0)
    np.testing.assert_array_equal(a, b)


def test_rectangle_mask_clamps_negatives():
    mask = rectangle_mask(4, 4, -10, -10, 1, 1)
    # Top-left 2x2 is selected; nothing else.
    assert mask[0, 0] and mask[1, 1]
    assert not mask[2, 2]


def test_rectangle_mask_rejects_zero_dimension():
    with pytest.raises(ValueError):
        rectangle_mask(0, 4, 0, 0, 1, 1)


# ---------------------------------------------------------------------------
# polygon_mask
# ---------------------------------------------------------------------------


def test_polygon_mask_triangle():
    pts = [(0, 0), (5, 0), (0, 5)]
    mask = polygon_mask(8, 8, pts)
    # Centre of triangle interior is filled.
    assert mask[1, 1]
    # Outside the triangle is not.
    assert not mask[6, 6]


def test_polygon_mask_under_three_points_is_empty():
    pts = [(0, 0), (5, 5)]
    mask = polygon_mask(8, 8, pts)
    assert mask.any() is np.False_ or mask.sum() == 0


def test_polygon_mask_rejects_zero_dimension():
    with pytest.raises(ValueError):
        polygon_mask(0, 8, [(0, 0), (1, 0), (0, 1)])


# ---------------------------------------------------------------------------
# magic_wand_mask
# ---------------------------------------------------------------------------


def test_magic_wand_picks_contiguous_region(canvas):
    mask = magic_wand_mask(canvas, 0, 0, tolerance=0)
    # White ring around the inner black square.
    assert mask[0, 0]
    assert not mask[6, 6]


def test_magic_wand_global_picks_all_matches(canvas):
    mask = magic_wand_mask(canvas, 6, 6, tolerance=0, contiguous=False)
    # 8x8 black inner square.
    assert mask.sum() == 8 * 8


def test_magic_wand_seed_off_canvas_is_empty(canvas):
    mask = magic_wand_mask(canvas, -1, -1)
    assert mask.sum() == 0


def test_magic_wand_rejects_non_rgba(sample_rgb_array):
    with pytest.raises(ValueError):
        magic_wand_mask(sample_rgb_array, 0, 0)


# ---------------------------------------------------------------------------
# Selection tool dispatchers
# ---------------------------------------------------------------------------


def _press(x, y):
    return PointerEvent(phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0)


def _move(x, y):
    return PointerEvent(phase="move", x=x, y=y, button=1, modifiers=0, pressure=1.0)


def _release(x, y):
    return PointerEvent(phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0)


def _make_ctx(state):
    """Build a SelectionContext over a local mutable cell."""
    holder: list[np.ndarray | None] = [None]

    def provider():
        return holder[0]

    def setter(mask):
        holder[0] = mask
    ctx = _SelectionContext(state, provider, setter)
    return ctx, holder


def test_rect_select_tool_drag_and_release_writes_mask(state, canvas):
    ctx, holder = _make_ctx(state)
    tool = RectSelectTool(ctx)
    tool.handle(_press(2, 2), canvas)
    tool.handle(_release(5, 5), canvas)
    assert holder[0] is not None
    assert holder[0][3, 3]
    assert not holder[0][0, 0]


def test_rect_select_release_without_press_returns_false(state, canvas):
    ctx, _ = _make_ctx(state)
    tool = RectSelectTool(ctx)
    assert tool.handle(_release(5, 5), canvas) is False


def test_lasso_select_tool_records_polygon(state, canvas):
    ctx, holder = _make_ctx(state)
    tool = LassoSelectTool(ctx)
    tool.handle(_press(0, 0), canvas)
    tool.handle(_move(5, 0), canvas)
    tool.handle(_move(0, 5), canvas)
    tool.handle(_release(0, 0), canvas)
    assert holder[0] is not None
    assert holder[0][1, 1]


def test_wand_select_tool_picks_seed_region(state, canvas):
    ctx, holder = _make_ctx(state)
    state.set_fill(tolerance=0, contiguous=True)
    tool = WandSelectTool(ctx, state)
    tool.handle(_press(0, 0), canvas)
    assert holder[0] is not None
    # White outer ring is selected.
    assert holder[0][0, 0]
    assert not holder[0][6, 6]


def test_rect_select_combines_via_state_mode(state, canvas):
    ctx, holder = _make_ctx(state)
    holder[0] = rectangle_mask(16, 16, 0, 0, 5, 5)  # existing selection
    state.set_selection_mode("subtract")
    tool = RectSelectTool(ctx)
    tool.handle(_press(2, 2), canvas)
    tool.handle(_release(8, 8), canvas)
    # The 2..5 overlap was subtracted.
    assert not holder[0][3, 3]
    assert holder[0][0, 0]


def test_rect_select_cancel_drops_pending_start(state, canvas):
    ctx, holder = _make_ctx(state)
    tool = RectSelectTool(ctx)
    tool.handle(_press(2, 2), canvas)
    tool.cancel()
    # Release after cancel should not write a mask.
    tool.handle(_release(5, 5), canvas)
    assert holder[0] is None


# ---------------------------------------------------------------------------
# ToolState selection_mode
# ---------------------------------------------------------------------------


def test_state_default_selection_mode_is_replace(state):
    assert state.selection_mode == "replace"


def test_set_selection_mode_persists(state):
    state.set_selection_mode("subtract")
    assert user_setting_dict["paint_state"]["selection_mode"] == "subtract"


def test_set_selection_mode_round_trips(state):
    state.set_selection_mode("intersect")
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.selection_mode == "intersect"


def test_set_selection_mode_rejects_unknown(state):
    with pytest.raises(ValueError):
        state.set_selection_mode("invert")


def test_set_selection_mode_idempotent_returns_false(state):
    state.set_selection_mode("add")
    assert state.set_selection_mode("add") is False


# ---------------------------------------------------------------------------
# Quick Select brush (28i)
# ---------------------------------------------------------------------------


def test_quick_select_in_tools_list():
    assert "select_quick" in ts.TOOLS


def test_quick_select_paints_first_sample(state, canvas):
    ctx, holder = _make_ctx(state)
    state.set_fill(tolerance=0, contiguous=True)
    tool = QuickSelectTool(ctx, state)
    tool.handle(_press(0, 0), canvas)
    tool.handle(_release(0, 0), canvas)
    assert holder[0] is not None
    # The white outer ring under the cursor is selected.
    assert holder[0][0, 0]
    # The black square middle was not visited.
    assert not holder[0][6, 6]


def test_quick_select_unions_multiple_samples(state, canvas):
    """Drag from a white pixel through a black pixel — both regions
    end up in the final selection."""
    ctx, holder = _make_ctx(state)
    state.set_fill(tolerance=0, contiguous=True)
    tool = QuickSelectTool(ctx, state)
    tool.handle(_press(0, 0), canvas)
    tool.handle(_move(6, 6), canvas)
    tool.handle(_release(6, 6), canvas)
    assert holder[0] is not None
    assert holder[0][0, 0]   # white ring
    assert holder[0][6, 6]   # black centre


def test_quick_select_cancel_drops_pending_strokes(state, canvas):
    ctx, holder = _make_ctx(state)
    state.set_fill(tolerance=0, contiguous=True)
    tool = QuickSelectTool(ctx, state)
    tool.handle(_press(0, 0), canvas)
    tool.cancel()
    tool.handle(_release(6, 6), canvas)
    # Release after cancel must not commit any selection.
    assert holder[0] is None


def test_quick_select_release_without_press_is_safe(state, canvas):
    """A stray release event before a press must not crash."""
    ctx, _holder = _make_ctx(state)
    tool = QuickSelectTool(ctx, state)
    # Should NOT raise.
    tool.handle(_release(0, 0), canvas)


def test_quick_select_respects_selection_combine_mode(state, canvas):
    """If the user picks 'subtract' before painting, the accumulated
    drag still lands as a subtract from the pre-stroke selection."""
    ctx, holder = _make_ctx(state)
    holder[0] = rectangle_mask(16, 16, 0, 0, 16, 16)   # full canvas selected
    state.set_fill(tolerance=0, contiguous=True)
    state.set_selection_mode("subtract")
    tool = QuickSelectTool(ctx, state)
    tool.handle(_press(6, 6), canvas)   # black centre region
    tool.handle(_release(6, 6), canvas)
    assert holder[0] is not None
    # Black centre subtracted; outer ring still selected.
    assert holder[0][0, 0]
    assert not holder[0][6, 6]
