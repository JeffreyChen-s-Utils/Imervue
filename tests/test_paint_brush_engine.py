"""Tests for the pure-numpy brush rasterisation engine."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.brush_engine import (
    BLEND_MODES,
    KERNEL_SIZE_MAX,
    KERNEL_SIZE_MIN,
    BrushStroke,
    BrushStrokeOptions,
    DabResult,
    apply_dab,
    round_brush_kernel,
    spacing_from_brush,
    stroke_dab_positions,
)


@pytest.fixture
def blank_canvas():
    """64×64 fully-transparent black canvas."""
    return np.zeros((64, 64, 4), dtype=np.uint8)


# ---------------------------------------------------------------------------
# round_brush_kernel
# ---------------------------------------------------------------------------


def test_kernel_returns_float32_in_unit_range():
    k = round_brush_kernel(15, hardness=0.5)
    assert k.dtype == np.float32
    assert k.min() >= 0.0
    assert k.max() <= 1.0


def test_kernel_size_one_is_solid_pixel():
    k = round_brush_kernel(1, hardness=0.5)
    assert k.shape == (1, 1)
    assert k[0, 0] == pytest.approx(1.0)


def test_kernel_hardness_one_is_step_disc():
    k = round_brush_kernel(11, hardness=1.0)
    centre = k[5, 5]
    assert centre == pytest.approx(1.0)
    # Far corner is outside the disc → 0.
    assert k[0, 0] == pytest.approx(0.0)


def test_kernel_hardness_zero_has_smooth_falloff():
    k = round_brush_kernel(11, hardness=0.0)
    centre = k[5, 5]
    edge = k[5, 10]
    # Strict gradient: centre brighter than edge.
    assert centre > edge


def test_kernel_clamps_size_above_max():
    k = round_brush_kernel(KERNEL_SIZE_MAX + 100, hardness=0.5)
    assert k.shape == (KERNEL_SIZE_MAX, KERNEL_SIZE_MAX)


def test_kernel_clamps_size_below_min():
    k = round_brush_kernel(KERNEL_SIZE_MIN - 5, hardness=0.5)
    assert k.shape == (KERNEL_SIZE_MIN, KERNEL_SIZE_MIN)


def test_kernel_clamps_hardness_above_one():
    a = round_brush_kernel(11, hardness=1.0)
    b = round_brush_kernel(11, hardness=5.0)
    np.testing.assert_array_equal(a, b)


# ---------------------------------------------------------------------------
# apply_dab — input validation
# ---------------------------------------------------------------------------


def test_apply_dab_rejects_non_rgba(sample_rgb_array):
    k = round_brush_kernel(7, hardness=1.0)
    with pytest.raises(ValueError):
        apply_dab(sample_rgb_array, 5, 5, k, (255, 0, 0))


def test_apply_dab_rejects_3d_kernel(blank_canvas):
    bad = np.ones((3, 3, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        apply_dab(blank_canvas, 5, 5, bad, (255, 0, 0))


def test_apply_dab_rejects_unknown_blend_mode(blank_canvas):
    k = round_brush_kernel(7, hardness=1.0)
    with pytest.raises(ValueError):
        apply_dab(blank_canvas, 5, 5, k, (255, 0, 0), blend_mode="vivid_glow")


# ---------------------------------------------------------------------------
# apply_dab — happy path
# ---------------------------------------------------------------------------


def test_apply_dab_paints_at_centre(blank_canvas):
    k = round_brush_kernel(7, hardness=1.0)
    apply_dab(blank_canvas, 32, 32, k, (255, 0, 0))
    assert blank_canvas[32, 32, 0] == 255
    # Outside the kernel radius nothing changed.
    assert blank_canvas[0, 0, 0] == 0


def test_apply_dab_returns_damage_rect(blank_canvas):
    k = round_brush_kernel(7, hardness=1.0)
    rect = apply_dab(blank_canvas, 32, 32, k, (255, 0, 0))
    assert rect.is_empty is False
    assert rect.w == 7
    assert rect.h == 7


def test_apply_dab_clips_off_canvas_corner(blank_canvas):
    k = round_brush_kernel(11, hardness=1.0)
    rect = apply_dab(blank_canvas, -2, -2, k, (255, 0, 0))
    # Half the dab is off-screen, the rest still paints.
    assert rect.is_empty is False
    assert rect.w < 11
    assert rect.h < 11


def test_apply_dab_fully_off_canvas_is_noop(blank_canvas):
    k = round_brush_kernel(7, hardness=1.0)
    rect = apply_dab(blank_canvas, -100, -100, k, (255, 0, 0))
    assert rect.is_empty
    assert blank_canvas.sum() == 0


def test_apply_dab_zero_opacity_is_noop(blank_canvas):
    k = round_brush_kernel(7, hardness=1.0)
    rect = apply_dab(blank_canvas, 32, 32, k, (255, 0, 0), opacity=0.0)
    assert rect.is_empty
    assert blank_canvas.sum() == 0


def test_apply_dab_alpha_accumulates(blank_canvas):
    k = round_brush_kernel(5, hardness=1.0)
    apply_dab(blank_canvas, 32, 32, k, (255, 0, 0))
    after_one = int(blank_canvas[32, 32, 3])
    apply_dab(blank_canvas, 32, 32, k, (255, 0, 0))
    after_two = int(blank_canvas[32, 32, 3])
    assert after_two >= after_one


# ---------------------------------------------------------------------------
# Blend modes — sanity (not a numerical reference suite)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", BLEND_MODES)
def test_each_blend_mode_runs_without_error(blank_canvas, mode):
    k = round_brush_kernel(5, hardness=1.0)
    rect = apply_dab(blank_canvas, 32, 32, k, (128, 128, 128), blend_mode=mode)
    assert rect.is_empty is False


def test_multiply_against_white_is_identity():
    canvas = np.full((11, 11, 4), 255, dtype=np.uint8)
    k = round_brush_kernel(11, hardness=1.0)
    apply_dab(canvas, 5, 5, k, (255, 0, 0), blend_mode="multiply")
    # White × red = red.
    centre = canvas[5, 5]
    assert centre[0] == 255
    assert centre[1] == 0
    assert centre[2] == 0


def test_screen_against_black_is_foreground():
    canvas = np.zeros((11, 11, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    k = round_brush_kernel(11, hardness=1.0)
    apply_dab(canvas, 5, 5, k, (200, 100, 50), blend_mode="screen")
    centre = canvas[5, 5]
    # Round-trip through float / uint8 may shift by 1 LSB.
    assert abs(int(centre[0]) - 200) <= 1
    assert abs(int(centre[1]) - 100) <= 1
    assert abs(int(centre[2]) - 50) <= 1


# ---------------------------------------------------------------------------
# stroke_dab_positions
# ---------------------------------------------------------------------------


def test_stroke_dab_positions_short_segment_returns_endpoint_only():
    out = stroke_dab_positions((0, 0), (1, 0), spacing=5)
    assert out == [(1.0, 0.0)]


def test_stroke_dab_positions_long_segment_uniformly_spaced():
    out = stroke_dab_positions((0, 0), (10, 0), spacing=2)
    # Five points: x ∈ {2, 4, 6, 8, 10}.
    assert len(out) == 5
    assert pytest.approx(out[0][0]) == 2.0
    assert pytest.approx(out[-1][0]) == 10.0


def test_stroke_dab_positions_includes_endpoint():
    out = stroke_dab_positions((0, 0), (7, 0), spacing=2)
    assert pytest.approx(out[-1][0]) == 7.0


def test_stroke_dab_positions_rejects_non_positive_spacing():
    with pytest.raises(ValueError):
        stroke_dab_positions((0, 0), (10, 0), spacing=0)


def test_spacing_from_brush_in_documented_range():
    s = spacing_from_brush(50, 0.5)
    assert 1.0 <= s <= 25.0


def test_spacing_from_brush_softer_brush_uses_finer_spacing():
    soft = spacing_from_brush(50, 0.0)
    hard = spacing_from_brush(50, 1.0)
    assert soft >= hard


# ---------------------------------------------------------------------------
# BrushStroke
# ---------------------------------------------------------------------------


def test_stroke_begin_paints_a_dab(blank_canvas):
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=7, opacity=1.0, hardness=1.0,
    ))
    stroke.begin(blank_canvas, 32, 32)
    assert blank_canvas[32, 32, 0] == 255


def test_stroke_extend_fills_gaps(blank_canvas):
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=3, opacity=1.0, hardness=1.0, spacing=1.0,
    ))
    stroke.begin(blank_canvas, 0, 32)
    stroke.extend(blank_canvas, 60, 32)
    # Every column between 0 and 60 received some red.
    red_columns = (blank_canvas[:, :, 0] == 255).any(axis=0)
    assert red_columns[0:60].all()


def test_stroke_begin_after_active_raises(blank_canvas):
    stroke = BrushStroke(BrushStrokeOptions(
        color=(0, 0, 0), size=5, opacity=1.0, hardness=1.0,
    ))
    stroke.begin(blank_canvas, 32, 32)
    with pytest.raises(RuntimeError):
        stroke.begin(blank_canvas, 0, 0)


def test_stroke_extend_before_begin_raises(blank_canvas):
    stroke = BrushStroke(BrushStrokeOptions(
        color=(0, 0, 0), size=5, opacity=1.0, hardness=1.0,
    ))
    with pytest.raises(RuntimeError):
        stroke.extend(blank_canvas, 5, 5)


def test_stroke_end_clears_active(blank_canvas):
    stroke = BrushStroke(BrushStrokeOptions(
        color=(0, 0, 0), size=5, opacity=1.0, hardness=1.0,
    ))
    stroke.begin(blank_canvas, 32, 32)
    stroke.end(blank_canvas, 33, 33)
    assert stroke.is_active is False


def test_dab_result_empty_property_matches_zero_dimensions():
    assert DabResult(0, 0, 0, 0).is_empty is True
    assert DabResult(0, 0, 1, 1).is_empty is False
