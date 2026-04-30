"""Tests for the flood fill bucket algorithm and its dispatcher hook."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.fill import FillResult, flood_fill
from Imervue.paint.tool_dispatcher import FillTool
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def chequer_canvas():
    """16×16 canvas with a black square inset on white background."""
    arr = np.full((16, 16, 4), 255, dtype=np.uint8)
    arr[4:12, 4:12, :3] = 0    # black square in the middle
    return arr


# ---------------------------------------------------------------------------
# flood_fill — input validation
# ---------------------------------------------------------------------------


def test_fill_rejects_non_rgba(sample_rgb_array):
    with pytest.raises(ValueError):
        flood_fill(sample_rgb_array, 0, 0, (255, 0, 0))


def test_fill_seed_off_canvas_returns_empty(chequer_canvas):
    out = flood_fill(chequer_canvas, -1, -1, (255, 0, 0))
    assert out.is_empty


def test_fill_clamps_negative_tolerance(chequer_canvas):
    a = flood_fill(chequer_canvas.copy(), 0, 0, (255, 0, 0), tolerance=0)
    b = flood_fill(chequer_canvas.copy(), 0, 0, (255, 0, 0), tolerance=-50)
    assert a.pixels_filled == b.pixels_filled


def test_fill_clamps_huge_tolerance(chequer_canvas):
    a = flood_fill(chequer_canvas.copy(), 0, 0, (255, 0, 0), tolerance=255)
    b = flood_fill(chequer_canvas.copy(), 0, 0, (255, 0, 0), tolerance=10_000)
    assert a.pixels_filled == b.pixels_filled


# ---------------------------------------------------------------------------
# Contiguous fill
# ---------------------------------------------------------------------------


def test_contiguous_fill_only_floods_seed_region(chequer_canvas):
    canvas = chequer_canvas.copy()
    out = flood_fill(canvas, 0, 0, (200, 0, 0), tolerance=0, contiguous=True)
    # White ring around the square is filled red.
    assert canvas[0, 0, 0] == 200
    # Inner black square untouched.
    assert canvas[6, 6, 0] == 0
    assert out.pixels_filled == (16 * 16) - (8 * 8)


def test_contiguous_fill_inside_returns_only_inner_square(chequer_canvas):
    canvas = chequer_canvas.copy()
    out = flood_fill(canvas, 6, 6, (0, 0, 200), tolerance=0, contiguous=True)
    assert out.pixels_filled == 8 * 8
    assert canvas[0, 0, 2] == 255   # outer ring untouched
    assert canvas[6, 6, 2] == 200


def test_contiguous_fill_records_full_alpha(chequer_canvas):
    canvas = chequer_canvas.copy()
    canvas[..., 3] = 0
    flood_fill(canvas, 0, 0, (50, 50, 50), tolerance=0)
    assert canvas[0, 0, 3] == 255


def test_contiguous_fill_isolated_seed_pixel():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[0, 0, 0] = 100
    out = flood_fill(canvas, 0, 0, (10, 20, 30), tolerance=0)
    # Only one pixel matched (R=100); others have R=0.
    assert out.pixels_filled == 1


# ---------------------------------------------------------------------------
# Global fill
# ---------------------------------------------------------------------------


def test_global_fill_paints_disconnected_islands():
    canvas = np.full((6, 6, 4), 255, dtype=np.uint8)
    canvas[1, 1, :3] = (10, 10, 10)
    canvas[4, 4, :3] = (10, 10, 10)
    out = flood_fill(canvas, 1, 1, (200, 0, 0), tolerance=0, contiguous=False)
    assert out.pixels_filled == 2
    assert canvas[1, 1, 0] == 200
    assert canvas[4, 4, 0] == 200


def test_global_fill_with_tolerance_picks_up_near_matches():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[0, 0, :3] = (100, 100, 100)
    canvas[3, 3, :3] = (110, 110, 110)
    out = flood_fill(canvas, 0, 0, (200, 0, 0), tolerance=15, contiguous=False)
    assert out.pixels_filled == 2


# ---------------------------------------------------------------------------
# FillResult
# ---------------------------------------------------------------------------


def test_fill_result_empty_property():
    assert FillResult(0, 0, 0, 0, 0).is_empty is True
    assert FillResult(0, 0, 4, 4, 16).is_empty is False


# ---------------------------------------------------------------------------
# FillTool dispatcher
# ---------------------------------------------------------------------------


def test_fill_tool_runs_on_press(chequer_canvas):
    state = ts.load_tool_state()
    state.set_foreground((255, 0, 0))
    state.set_fill(tolerance=0, contiguous=True)
    tool = FillTool(state)
    evt = PointerEvent(phase="press", x=0, y=0, button=1, modifiers=0, pressure=1.0)
    canvas = chequer_canvas.copy()
    assert tool.handle(evt, canvas) is True
    assert canvas[0, 0, 0] == 255


def test_fill_tool_ignores_move(chequer_canvas):
    state = ts.load_tool_state()
    tool = FillTool(state)
    evt = PointerEvent(phase="move", x=0, y=0, button=1, modifiers=0, pressure=1.0)
    canvas = chequer_canvas.copy()
    assert tool.handle(evt, canvas) is False


# ---------------------------------------------------------------------------
# ToolState fill round-trip
# ---------------------------------------------------------------------------


def test_set_fill_persists_to_dict():
    state = ts.load_tool_state()
    state.set_fill(tolerance=128, contiguous=False, sample_all_layers=True)
    raw = user_setting_dict["paint_state"]
    assert raw["fill"]["tolerance"] == 128
    assert raw["fill"]["contiguous"] is False
    assert raw["fill"]["sample_all_layers"] is True


def test_set_fill_round_trips_via_to_from_dict():
    state = ts.load_tool_state()
    state.set_fill(tolerance=64, contiguous=False)
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.fill.tolerance == 64
    assert rebuilt.fill.contiguous is False


def test_set_fill_clamps_tolerance_above_max():
    state = ts.load_tool_state()
    state.set_fill(tolerance=ts.FILL_TOLERANCE_MAX + 100)
    assert state.fill.tolerance == ts.FILL_TOLERANCE_MAX


def test_set_fill_idempotent_returns_false():
    state = ts.load_tool_state()
    state.set_fill(tolerance=64)
    assert state.set_fill(tolerance=64) is False


def test_set_fill_rejects_unknown_attribute():
    state = ts.load_tool_state()
    with pytest.raises(ValueError):
        state.set_fill(magic_wand_size=8)
