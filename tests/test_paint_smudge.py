"""Tests for the smudge / mixer brush algorithm."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.brush_engine import round_brush_kernel
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.smudge import sample_carry, smudge_dab
from Imervue.paint.tool_dispatcher import SmudgeTool
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def kernel():
    return round_brush_kernel(7, hardness=1.0)


@pytest.fixture
def canvas():
    """32×32 canvas split into red (left half) and blue (right half)."""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)
    arr[..., 3] = 255
    arr[:, :16, 0] = 255
    arr[:, 16:, 2] = 255
    return arr


# ---------------------------------------------------------------------------
# sample_carry
# ---------------------------------------------------------------------------


def test_sample_carry_returns_kernel_shaped_buffer(canvas, kernel):
    out = sample_carry(canvas, 16, 16, kernel)
    assert out.shape == (*kernel.shape, 4)
    assert out.dtype == np.uint8


def test_sample_carry_off_canvas_returns_zeros(canvas, kernel):
    out = sample_carry(canvas, -100, -100, kernel)
    assert out.shape == (*kernel.shape, 4)
    assert (out == 0).all()


def test_sample_carry_clips_partial_overlap(canvas, kernel):
    """Centre at top-left edge — only a slice of the canvas is sampled."""
    out = sample_carry(canvas, 0, 0, kernel)
    # The first row / column should be zero (off-canvas).
    assert (out[0, :].sum() == 0)


def test_sample_carry_rejects_non_rgba(sample_rgb_array, kernel):
    with pytest.raises(ValueError):
        sample_carry(sample_rgb_array, 5, 5, kernel)


# ---------------------------------------------------------------------------
# smudge_dab
# ---------------------------------------------------------------------------


def test_smudge_dab_drags_red_into_blue(canvas, kernel):
    carried = sample_carry(canvas, 8, 16, kernel)   # pure red snapshot
    # Drag the red carry into the blue half.
    _result, _ = smudge_dab(
        canvas, 18, 16, kernel, carried, strength=1.0, decay=0.0,
    )
    # The dab centre at x=18 was blue; now it has some red mixed in.
    assert canvas[16, 18, 0] > 50


def test_smudge_dab_zero_strength_is_noop(canvas, kernel):
    carried = sample_carry(canvas, 8, 16, kernel)
    snapshot = canvas.copy()
    smudge_dab(canvas, 18, 16, kernel, carried, strength=0.0)
    np.testing.assert_array_equal(canvas, snapshot)


def test_smudge_dab_returns_updated_carry(canvas, kernel):
    carried = sample_carry(canvas, 8, 16, kernel)   # red
    _, new_carry = smudge_dab(
        canvas, 18, 16, kernel, carried, strength=1.0, decay=1.0,
    )
    # decay=1.0 → carry is replaced by (modified) canvas content.
    assert not np.array_equal(new_carry, carried)


def test_smudge_dab_decay_zero_keeps_carry(canvas, kernel):
    carried = sample_carry(canvas, 8, 16, kernel)
    _, new_carry = smudge_dab(
        canvas, 18, 16, kernel, carried, strength=1.0, decay=0.0,
    )
    # decay=0 → carry unchanged in the slice that was active.
    np.testing.assert_array_equal(new_carry, carried)


def test_smudge_dab_off_canvas_returns_empty(canvas, kernel):
    carried = sample_carry(canvas, 8, 16, kernel)
    snapshot = canvas.copy()
    result, _ = smudge_dab(
        canvas, -100, -100, kernel, carried, strength=1.0,
    )
    assert result.is_empty
    np.testing.assert_array_equal(canvas, snapshot)


def test_smudge_dab_rejects_carry_shape_mismatch(canvas, kernel):
    bad_carry = np.zeros((3, 3, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        smudge_dab(canvas, 16, 16, kernel, bad_carry)


def test_smudge_dab_rejects_selection_shape_mismatch(canvas, kernel):
    carried = sample_carry(canvas, 8, 16, kernel)
    bad_sel = np.zeros((10, 10), dtype=np.bool_)
    with pytest.raises(ValueError):
        smudge_dab(canvas, 16, 16, kernel, carried, selection=bad_sel)


def test_smudge_dab_respects_selection(canvas, kernel):
    carried = sample_carry(canvas, 8, 16, kernel)
    sel = np.zeros(canvas.shape[:2], dtype=np.bool_)
    sel[10:22, 14:22] = True
    snapshot = canvas.copy()
    smudge_dab(canvas, 18, 16, kernel, carried, strength=1.0, selection=sel)
    # Outside the selection: canvas unchanged.
    assert canvas[0, 0, 0] == snapshot[0, 0, 0]


def test_smudge_dab_clamps_strength_above_max(canvas, kernel):
    carried = sample_carry(canvas, 8, 16, kernel)
    a = canvas.copy()
    smudge_dab(a, 18, 16, kernel, carried, strength=1.0)
    b = canvas.copy()
    smudge_dab(b, 18, 16, kernel, carried, strength=5.0)
    np.testing.assert_array_equal(a, b)


# ---------------------------------------------------------------------------
# SmudgeTool dispatcher
# ---------------------------------------------------------------------------


def _press(x, y):
    return PointerEvent(phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0)


def _move(x, y):
    return PointerEvent(phase="move", x=x, y=y, button=1, modifiers=0, pressure=1.0)


def _release(x, y):
    return PointerEvent(phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0)


def test_smudge_tool_press_alone_returns_false(canvas):
    state = ts.load_tool_state()
    state.set_brush(size=5, opacity=1.0, hardness=1.0)
    tool = SmudgeTool(state, lambda: None)
    assert tool.handle(_press(8, 16), canvas) is False


def test_smudge_tool_drag_smudges(canvas):
    state = ts.load_tool_state()
    state.set_brush(size=5, opacity=1.0, hardness=1.0)
    tool = SmudgeTool(state, lambda: None)
    tool.handle(_press(8, 16), canvas)
    assert tool.handle(_move(18, 16), canvas) is True
    # Some red bled into the previously-blue right half.
    assert canvas[16, 18, 0] > 30


def test_smudge_tool_move_without_press_returns_false(canvas):
    state = ts.load_tool_state()
    tool = SmudgeTool(state, lambda: None)
    assert tool.handle(_move(5, 5), canvas) is False


def test_smudge_tool_release_clears_state(canvas):
    state = ts.load_tool_state()
    state.set_brush(size=5, opacity=1.0, hardness=1.0)
    tool = SmudgeTool(state, lambda: None)
    tool.handle(_press(8, 16), canvas)
    tool.handle(_move(18, 16), canvas)
    tool.handle(_release(18, 16), canvas)
    # After release, a move should be ignored.
    snapshot = canvas.copy()
    tool.handle(_move(20, 16), canvas)
    np.testing.assert_array_equal(canvas, snapshot)


def test_smudge_tool_cancel_drops_active_state(canvas):
    state = ts.load_tool_state()
    tool = SmudgeTool(state, lambda: None)
    tool.handle(_press(8, 16), canvas)
    tool.cancel()
    assert tool.handle(_move(18, 16), canvas) is False
