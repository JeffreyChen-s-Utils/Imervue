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
    apply_erase_dab,
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


def test_apply_erase_dab_clears_rgb_on_full_alpha_drop():
    """An eraser pass that fully clears alpha must also wipe RGB —
    a later soft brush over the erased pixel would otherwise pull
    the previous colour into its anti-aliased edge."""
    canvas = np.zeros((11, 11, 4), dtype=np.uint8)
    canvas[..., 0] = 0
    canvas[..., 1] = 0
    canvas[..., 2] = 200
    canvas[..., 3] = 255
    k = round_brush_kernel(7, hardness=1.0)   # solid disc → alpha drops to 0
    apply_erase_dab(canvas, 5, 5, k, opacity=1.0)
    # Every pixel inside the disc has alpha 0 AND every channel zero.
    centre = canvas[5, 5]
    assert int(centre[3]) == 0
    assert int(centre[0]) == 0
    assert int(centre[1]) == 0
    assert int(centre[2]) == 0


def test_apply_erase_dab_keeps_rgb_when_alpha_drops_partially():
    """A soft eraser that leaves alpha > 0 must keep RGB — those
    pixels are still partially visible so the colour still matters."""
    canvas = np.zeros((11, 11, 4), dtype=np.uint8)
    canvas[..., :3] = (200, 50, 50)
    canvas[..., 3] = 255
    k = round_brush_kernel(7, hardness=0.0)   # soft falloff
    apply_erase_dab(canvas, 5, 5, k, opacity=0.4)   # only partial drop
    # Find a pixel inside the dab whose alpha is still non-zero — its
    # RGB must still be the original red.
    inside = canvas[5, 8]   # away from centre, soft edge → partial drop
    if int(inside[3]) > 0:
        assert int(inside[0]) == 200
        assert int(inside[1]) == 50
        assert int(inside[2]) == 50


def test_apply_dab_over_transparent_pixel_uses_fg_color(blank_canvas):
    """Painting onto an alpha=0 pixel that still carries lingering
    RGB (left over from a previous erase) must deposit the
    foreground colour directly — not a low-alpha mix of fg with the
    stale RGB. Otherwise the soft edges of a new stroke would show
    a halo of whatever colour used to be there."""
    # Stage: lingering blue at full RGB, alpha=0 (post-erase state).
    blank_canvas[..., 0] = 0
    blank_canvas[..., 1] = 0
    blank_canvas[..., 2] = 200
    blank_canvas[..., 3] = 0
    k = round_brush_kernel(11, hardness=0.0)   # soft brush — edges are partial
    apply_dab(blank_canvas, 32, 32, k, (255, 0, 0))
    # Edge of the dab — partial alpha. Without the fix the result
    # would pull blue (lingering) toward red (fg) and produce a
    # purple halo. With the fix, the deposited colour is pure red
    # because bg was substituted with fg before the mix.
    centre = blank_canvas[32, 32]
    edge = blank_canvas[32, 28]
    for px in (centre, edge):
        if px[3] > 0:
            assert int(px[0]) > 200, f"red channel low at {px}"
            assert int(px[2]) <= 50, f"blue contamination at {px}"


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
    assert pytest.approx(out[0][0]) == pytest.approx(2.0)
    assert pytest.approx(out[-1][0]) == pytest.approx(10.0)


def test_stroke_dab_positions_includes_endpoint():
    out = stroke_dab_positions((0, 0), (7, 0), spacing=2)
    assert pytest.approx(out[-1][0]) == pytest.approx(7.0)


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


# ---------------------------------------------------------------------------
# Pixel-art mode (28e)
# ---------------------------------------------------------------------------


def test_square_brush_kernel_is_all_ones():
    from Imervue.paint.brush_engine import square_brush_kernel
    kernel = square_brush_kernel(5)
    assert kernel.shape == (5, 5)
    assert kernel.dtype == np.float32
    assert np.allclose(kernel, 1.0)


def test_square_brush_kernel_clamps_size():
    from Imervue.paint.brush_engine import square_brush_kernel
    huge = square_brush_kernel(10_000)
    assert huge.shape[0] <= KERNEL_SIZE_MAX
    tiny = square_brush_kernel(0)
    assert tiny.shape[0] >= KERNEL_SIZE_MIN


def test_pixel_art_mode_uses_square_kernel(blank_canvas):
    """A 3-px pixel-art dab fills exactly a 3x3 square at integer pos."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=3, opacity=1.0, hardness=1.0,
        pixel_art=True,
    ))
    # Aim at integer (32, 32) so the centred 3x3 stamp lands at
    # rows / cols 31..33 without snap ambiguity.
    stroke.begin(blank_canvas, 32, 32)
    region = blank_canvas[31:34, 31:34, 0]
    assert (region == 255).all()


def test_pixel_art_mode_snaps_to_integer_position(blank_canvas):
    """Fractional coordinates must round to integers — the dab stamp
    therefore lands on an aligned 3x3 grid."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=1, opacity=1.0, hardness=1.0,
        pixel_art=True,
    ))
    stroke.begin(blank_canvas, 32.7, 32.3)
    # Round to (33, 32).
    assert blank_canvas[32, 33, 0] == 255
    # Adjacent fractional cells stay untouched.
    assert blank_canvas[32, 32, 0] == 0
    assert blank_canvas[33, 33, 0] == 0


def test_pixel_art_mode_ignores_hardness_falloff(blank_canvas):
    """Even with hardness=0 (smooth round brush), pixel_art forces a
    hard square — no fractional alpha at the kernel edge."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 255, 255), size=5, opacity=1.0, hardness=0.0,
        pixel_art=True,
    ))
    stroke.begin(blank_canvas, 32, 32)
    region = blank_canvas[30:35, 30:35, 3]
    # Every cell in the 5x5 stamp is fully opaque.
    assert (region == 255).all()


def test_pixel_art_mode_off_keeps_anti_aliased_edges(blank_canvas):
    """Without pixel_art the dab uses the standard round kernel, so
    the corners of a 5x5 region are NOT all fully opaque."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 255, 255), size=5, opacity=1.0, hardness=0.0,
        pixel_art=False,
    ))
    stroke.begin(blank_canvas, 32, 32)
    corners = blank_canvas[[30, 30, 34, 34], [30, 34, 30, 34], 3]
    # At least one corner has alpha < 255 (AA falloff).
    assert (corners < 255).any()


def test_pixel_art_mode_extend_snaps_dab_positions(blank_canvas):
    """Continuing a stroke at a fractional position must also snap
    so the stroke trails through integer pixels."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=1, opacity=1.0, hardness=1.0,
        pixel_art=True,
    ))
    stroke.begin(blank_canvas, 32, 32)
    stroke.extend(blank_canvas, 35.4, 32.0)
    assert blank_canvas[32, 35, 0] == 255
    # Off-axis intermediate dab positions are also integer-snapped —
    # no fractional dab between (32, 32) and (35, 32).
    assert blank_canvas[32, 33, 0] in (0, 255)


def test_pixel_art_mode_default_is_off():
    options = BrushStrokeOptions(
        color=(0, 0, 0), size=4, opacity=1.0, hardness=1.0,
    )
    assert options.pixel_art is False


# ---------------------------------------------------------------------------
# Tapered stroke (29g)
# ---------------------------------------------------------------------------


def test_taper_options_default_to_zero():
    options = BrushStrokeOptions(
        color=(0, 0, 0), size=4, opacity=1.0, hardness=1.0,
    )
    assert options.taper_start_dabs == 0
    assert options.taper_end_dabs == 0


def test_start_taper_ramps_first_dab_softer_than_steady(blank_canvas):
    """With taper_start_dabs=4 the first dab paints with 1/4 of full
    opacity, so its alpha is materially lower than a later dab."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=3, opacity=1.0, hardness=1.0,
        taper_start_dabs=4,
    ))
    stroke.begin(blank_canvas, 10, 10)
    first_alpha = int(blank_canvas[10, 10, 3])
    # Move far enough to lay down several follow-up dabs at a fresh
    # spot; pick one well past the taper window.
    stroke.end(blank_canvas, 30, 10)
    later_alpha = int(blank_canvas[10, 30, 3])
    assert first_alpha < later_alpha


def test_no_start_taper_yields_uniform_alpha(blank_canvas):
    """Without taper_start_dabs the first and later dabs match."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=3, opacity=1.0, hardness=1.0,
    ))
    stroke.begin(blank_canvas, 10, 10)
    first_alpha = int(blank_canvas[10, 10, 3])
    stroke.end(blank_canvas, 30, 10)
    later_alpha = int(blank_canvas[10, 30, 3])
    assert first_alpha == later_alpha


def test_end_taper_buffers_and_fades_tail(blank_canvas):
    """A long stroke with taper_end_dabs=4 ends with a tail of dabs
    progressively fainter than the steady-state segment."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=3, opacity=1.0, hardness=1.0,
        taper_end_dabs=4,
    ))
    stroke.begin(blank_canvas, 5, 30)
    stroke.end(blank_canvas, 55, 30)
    # Pixel near the start (post-taper-window) is at full alpha.
    mid_alpha = int(blank_canvas[30, 25, 3])
    # Pixel near the very end is in the tail-fade window.
    tail_alpha = int(blank_canvas[30, 54, 3])
    assert mid_alpha > tail_alpha


def test_no_end_taper_keeps_tail_at_full_alpha(blank_canvas):
    """Without taper_end_dabs the last dab is at full alpha."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=3, opacity=1.0, hardness=1.0,
    ))
    stroke.begin(blank_canvas, 5, 30)
    stroke.end(blank_canvas, 55, 30)
    tail_alpha = int(blank_canvas[30, 54, 3])
    assert tail_alpha == 255


def test_combined_start_and_end_taper(blank_canvas):
    """Both ends fade. Middle is at full opacity, both ends weaker."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=(255, 0, 0), size=3, opacity=1.0, hardness=1.0,
        taper_start_dabs=4, taper_end_dabs=4,
    ))
    stroke.begin(blank_canvas, 5, 30)
    stroke.end(blank_canvas, 55, 30)
    head_alpha = int(blank_canvas[30, 5, 3])
    mid_alpha = int(blank_canvas[30, 30, 3])
    tail_alpha = int(blank_canvas[30, 54, 3])
    assert mid_alpha > head_alpha
    assert mid_alpha > tail_alpha
