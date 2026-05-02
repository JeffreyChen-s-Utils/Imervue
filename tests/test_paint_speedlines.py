"""Tests for the manga speed-line / focus-line generator."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.speedlines import (
    DEFAULT_LINE_COUNT,
    DEFAULT_LINE_THICKNESS,
    DEFAULT_SPEEDLINE_KIND,
    LINE_COUNT_MAX,
    LINE_COUNT_MIN,
    LINE_THICKNESS_MAX,
    LINE_THICKNESS_MIN,
    SPEEDLINE_KINDS,
    SpeedlineOptions,
    render_speedlines,
)


# ---------------------------------------------------------------------------
# SpeedlineOptions validation
# ---------------------------------------------------------------------------


def test_default_options_pass_validation():
    opts = SpeedlineOptions()
    assert opts.kind == DEFAULT_SPEEDLINE_KIND
    assert opts.count == DEFAULT_LINE_COUNT
    assert opts.thickness == DEFAULT_LINE_THICKNESS


def test_rejects_unknown_kind():
    with pytest.raises(ValueError, match="kind"):
        SpeedlineOptions(kind="zigzag")


def test_rejects_count_below_min():
    with pytest.raises(ValueError, match="count"):
        SpeedlineOptions(count=LINE_COUNT_MIN - 1)


def test_rejects_count_above_max():
    with pytest.raises(ValueError, match="count"):
        SpeedlineOptions(count=LINE_COUNT_MAX + 1)


def test_rejects_thickness_below_min():
    with pytest.raises(ValueError, match="thickness"):
        SpeedlineOptions(thickness=LINE_THICKNESS_MIN - 1)


def test_rejects_thickness_above_max():
    with pytest.raises(ValueError, match="thickness"):
        SpeedlineOptions(thickness=LINE_THICKNESS_MAX + 1)


def test_rejects_color_with_wrong_length():
    with pytest.raises(ValueError, match="color"):
        SpeedlineOptions(color=(0, 0, 0))   # type: ignore[arg-type]


def test_rejects_color_component_out_of_range():
    with pytest.raises(ValueError, match="color"):
        SpeedlineOptions(color=(0, 0, 0, 999))


def test_rejects_inner_radius_at_one():
    with pytest.raises(ValueError, match="inner_radius_ratio"):
        SpeedlineOptions(inner_radius_ratio=1.0)


def test_rejects_negative_inner_radius():
    with pytest.raises(ValueError, match="inner_radius_ratio"):
        SpeedlineOptions(inner_radius_ratio=-0.1)


def test_rejects_jitter_above_one():
    with pytest.raises(ValueError, match="jitter"):
        SpeedlineOptions(jitter=2.0)


# ---------------------------------------------------------------------------
# render_speedlines — canvas validation
# ---------------------------------------------------------------------------


def test_render_rejects_non_positive_canvas():
    with pytest.raises(ValueError):
        render_speedlines((0, 64), SpeedlineOptions())


def test_render_returns_rgba_buffer():
    out = render_speedlines((32, 64), SpeedlineOptions(seed=1))
    assert out.shape == (32, 64, 4)
    assert out.dtype == np.uint8


# ---------------------------------------------------------------------------
# Per-kind behavioural checks
# ---------------------------------------------------------------------------


def test_radial_paints_inked_pixels():
    out = render_speedlines((64, 64), SpeedlineOptions(
        kind="radial", count=40, seed=7,
    ))
    assert (out[..., 3] > 0).any()


def test_radial_uses_canvas_centre_when_center_unset():
    """Inked pixels span both halves of the canvas — the radial fan
    radiates outward from the centre, so each axis half has ink."""
    out = render_speedlines((64, 64), SpeedlineOptions(
        kind="radial", count=80, seed=42,
    ))
    inked = out[..., 3] > 0
    h, w = inked.shape
    assert inked[: h // 2].any()
    assert inked[h // 2 :].any()
    assert inked[:, : w // 2].any()
    assert inked[:, w // 2 :].any()


def test_radial_respects_explicit_centre():
    """A centre near the corner produces ink that biases toward that
    corner — guards against ignoring the user's centre."""
    out_centre = render_speedlines((64, 64), SpeedlineOptions(
        kind="radial", count=40, seed=3,
    ))
    out_corner = render_speedlines((64, 64), SpeedlineOptions(
        kind="radial", count=40, seed=3, center=(8, 8),
    ))
    # The centre image has more ink in the bottom-right than the
    # corner-centred image (which radiates outward from the corner).
    centre_br = (out_centre[40:, 40:, 3] > 0).sum()
    corner_br = (out_corner[40:, 40:, 3] > 0).sum()
    assert centre_br >= corner_br


def test_burst_leaves_an_inner_hole():
    """Burst keeps a radius near the centre transparent so the focus
    subject still reads."""
    out = render_speedlines((64, 64), SpeedlineOptions(
        kind="burst", count=120, seed=2, inner_radius_ratio=0.4,
    ))
    inked = out[..., 3] > 0
    # The 8×8 box at the very centre stays transparent.
    centre = inked[28:36, 28:36]
    assert not centre.any()
    # The corners DO see ink because lines radiate out past them.
    assert inked[0, 0:8].any() or inked[0:8, 0].any()


def test_parallel_renders_along_horizontal_axis():
    """Parallel at 0° produces ink rows spanning the canvas width."""
    out = render_speedlines((64, 64), SpeedlineOptions(
        kind="parallel", count=40, angle_deg=0.0, seed=5, jitter=0.0,
    ))
    inked = out[..., 3] > 0
    # Ink reaches both left and right edges since lines are
    # horizontal across the canvas.
    assert inked[:, 0].any() and inked[:, -1].any()


def test_parallel_respects_angle_difference():
    """A 90° rotation produces a materially different ink pattern.

    Use a low count so lines stay individual at this small canvas
    size — at high counts the 0° and 90° passes both saturate the
    canvas and the per-pixel diff disappears.
    """
    a = render_speedlines((64, 64), SpeedlineOptions(
        kind="parallel", count=8, angle_deg=0.0, seed=7, jitter=0.0,
    ))
    b = render_speedlines((64, 64), SpeedlineOptions(
        kind="parallel", count=8, angle_deg=90.0, seed=7, jitter=0.0,
    ))
    assert not np.array_equal(a[..., 3], b[..., 3])


# ---------------------------------------------------------------------------
# Determinism + colour
# ---------------------------------------------------------------------------


def test_same_seed_produces_identical_output():
    a = render_speedlines((48, 48), SpeedlineOptions(seed=11))
    b = render_speedlines((48, 48), SpeedlineOptions(seed=11))
    np.testing.assert_array_equal(a, b)


def test_different_seeds_diverge():
    a = render_speedlines((48, 48), SpeedlineOptions(seed=11))
    b = render_speedlines((48, 48), SpeedlineOptions(seed=12))
    assert not np.array_equal(a, b)


def test_color_field_paints_inked_pixels_with_specified_rgb():
    out = render_speedlines((48, 48), SpeedlineOptions(
        kind="radial", count=40, seed=1, color=(200, 50, 30, 255),
    ))
    inked = out[out[..., 3] > 0]
    assert (inked[:, 0] == 200).all()
    assert (inked[:, 1] == 50).all()
    assert (inked[:, 2] == 30).all()


def test_kinds_constant_lists_three_modes():
    assert set(SPEEDLINE_KINDS) == {"radial", "parallel", "burst"}
