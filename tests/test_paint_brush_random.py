"""Tests for per-dab brush randomisation helpers."""
from __future__ import annotations

import math

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.brush_random import (
    jitter_color,
    rotate_kernel,
    scatter_offset,
    tilt_rotation_radians,
)


# ---------------------------------------------------------------------------
# scatter_offset
# ---------------------------------------------------------------------------


def test_scatter_zero_returns_origin():
    rng = np.random.default_rng(seed=0)
    assert scatter_offset(20, 0.0, rng) == (0.0, 0.0)


def test_scatter_offset_within_radius():
    rng = np.random.default_rng(seed=42)
    for _ in range(50):
        dx, dy = scatter_offset(20, 0.5, rng)
        assert math.hypot(dx, dy) <= 20 * 0.5 + 1e-6


def test_scatter_deterministic_with_seed():
    a = scatter_offset(20, 0.5, np.random.default_rng(seed=7))
    b = scatter_offset(20, 0.5, np.random.default_rng(seed=7))
    assert a == b


def test_scatter_negative_short_circuits_to_origin():
    rng = np.random.default_rng(seed=0)
    assert scatter_offset(20, -0.1, rng) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# jitter_color
# ---------------------------------------------------------------------------


def test_color_jitter_zero_returns_input():
    rng = np.random.default_rng(seed=0)
    assert jitter_color((100, 50, 200), 0.0, rng) == (100, 50, 200)


def test_color_jitter_returns_uint8_tuple():
    rng = np.random.default_rng(seed=1)
    out = jitter_color((100, 50, 200), 0.5, rng)
    assert isinstance(out, tuple)
    assert len(out) == 3
    for c in out:
        assert isinstance(c, int)
        assert 0 <= c <= 255


def test_color_jitter_perturbs_off_input():
    rng = np.random.default_rng(seed=42)
    perturbed = jitter_color((100, 100, 100), 0.8, rng)
    # Strong jitter on a mid-grey should differ from the input.
    assert perturbed != (100, 100, 100)


def test_color_jitter_deterministic_with_seed():
    a = jitter_color((100, 50, 200), 0.5, np.random.default_rng(seed=99))
    b = jitter_color((100, 50, 200), 0.5, np.random.default_rng(seed=99))
    assert a == b


# ---------------------------------------------------------------------------
# tilt_rotation_radians
# ---------------------------------------------------------------------------


def test_tilt_zero_returns_zero():
    assert tilt_rotation_radians(0.0, 0.0) == 0.0


def test_tilt_positive_x_yields_zero_angle():
    """Tilt purely along +x → angle 0 radians (kernel unchanged)."""
    assert tilt_rotation_radians(0.5, 0.0) == pytest.approx(0.0)


def test_tilt_positive_y_yields_quarter_turn():
    assert tilt_rotation_radians(0.0, 0.5) == pytest.approx(math.pi / 2)


def test_tilt_diagonal_returns_45_degrees():
    angle = tilt_rotation_radians(0.5, 0.5)
    assert angle == pytest.approx(math.pi / 4)


# ---------------------------------------------------------------------------
# rotate_kernel
# ---------------------------------------------------------------------------


def test_rotate_kernel_zero_angle_returns_unchanged():
    kernel = np.eye(5, dtype=np.float32)
    out = rotate_kernel(kernel, 0.0)
    np.testing.assert_array_equal(out, kernel)


def test_rotate_kernel_returns_contiguous_float32():
    kernel = np.ones((5, 5), dtype=np.float32)
    out = rotate_kernel(kernel, math.pi / 4)
    assert out.dtype == np.float32
    assert out.flags["C_CONTIGUOUS"]


def test_rotate_kernel_quarter_turn_swaps_axes():
    """A diagonal-stripe kernel rotated 90° flips its diagonal."""
    kernel = np.zeros((5, 5), dtype=np.float32)
    np.fill_diagonal(kernel, 1.0)
    out = rotate_kernel(kernel, math.pi / 2)
    # After 90° CCW the diagonal becomes the anti-diagonal.
    np.testing.assert_allclose(out[0, 4], 1.0, atol=1e-3)
    np.testing.assert_allclose(out[4, 0], 1.0, atol=1e-3)


def test_rotate_kernel_rejects_non_2d():
    with pytest.raises(ValueError, match="2-D"):
        rotate_kernel(np.zeros((5, 5, 3), dtype=np.float32), 0.5)


# ---------------------------------------------------------------------------
# BrushSettings field round-trip
# ---------------------------------------------------------------------------


def test_brush_settings_carries_new_fields():
    bs = ts.BrushSettings(scatter=0.5, color_jitter=0.3, follow_tilt=True)
    assert bs.scatter == 0.5
    assert bs.color_jitter == 0.3
    assert bs.follow_tilt is True


def test_set_brush_clamps_scatter_above_one():
    state = ts.ToolState()
    state.set_brush(scatter=2.0)
    assert state.brush.scatter == 1.0


def test_set_brush_clamps_color_jitter_below_zero():
    state = ts.ToolState()
    state.set_brush(color_jitter=-0.5)
    assert state.brush.color_jitter == 0.0


def test_set_brush_follow_tilt_coerces_to_bool():
    state = ts.ToolState()
    state.set_brush(follow_tilt=1)
    assert state.brush.follow_tilt is True


def test_brush_settings_round_trip_via_tool_state_dict():
    state = ts.ToolState()
    state.set_brush(scatter=0.6, color_jitter=0.2, follow_tilt=True)
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.brush.scatter == pytest.approx(0.6)
    assert rebuilt.brush.color_jitter == pytest.approx(0.2)
    assert rebuilt.brush.follow_tilt is True
