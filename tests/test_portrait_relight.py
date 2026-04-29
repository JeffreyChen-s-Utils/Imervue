"""Tests for the AI Portrait Relighting plugin's algorithm layer."""
from __future__ import annotations

import numpy as np
import pytest

from ai_portrait_relight.relight import (
    AZIMUTH_MAX,
    BLEND_MAX,
    ELEVATION_MIN,
    INTENSITY_MAX,
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    RelightOptions,
    heuristic_relight,
    light_direction,
)


# ---------------------------------------------------------------------------
# light_direction unit vector
# ---------------------------------------------------------------------------


def test_light_direction_returns_unit_vector():
    vec = light_direction(45, 30)
    assert pytest.approx(1.0, abs=1e-6) == float(np.linalg.norm(vec))


def test_light_direction_zero_az_zero_el_points_right():
    vec = light_direction(0, 0)
    np.testing.assert_allclose(vec, np.array([1.0, 0.0, 0.0]), atol=1e-6)


def test_light_direction_clamps_azimuth_above_max():
    over = light_direction(AZIMUTH_MAX + 100, 0)
    cap = light_direction(AZIMUTH_MAX, 0)
    np.testing.assert_allclose(over, cap, atol=1e-6)


def test_light_direction_clamps_elevation_below_min():
    under = light_direction(0, ELEVATION_MIN - 50)
    cap = light_direction(0, ELEVATION_MIN)
    np.testing.assert_allclose(under, cap, atol=1e-6)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_relight_rejects_non_rgba(sample_rgb_array):
    with pytest.raises(ValueError):
        heuristic_relight(sample_rgb_array)


def test_relight_rejects_non_uint8():
    arr = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        heuristic_relight(arr)


# ---------------------------------------------------------------------------
# Happy path / shape
# ---------------------------------------------------------------------------


def test_relight_returns_same_shape_and_dtype(sample_rgba_array):
    out = heuristic_relight(sample_rgba_array)
    assert out.shape == sample_rgba_array.shape
    assert out.dtype == np.uint8


def test_relight_preserves_alpha(sample_rgba_array):
    out = heuristic_relight(sample_rgba_array)
    np.testing.assert_array_equal(out[..., 3], sample_rgba_array[..., 3])


# ---------------------------------------------------------------------------
# Blend behaviour
# ---------------------------------------------------------------------------


def test_relight_blend_zero_returns_copy(sample_rgba_array):
    out = heuristic_relight(sample_rgba_array, RelightOptions(blend=0.0))
    np.testing.assert_array_equal(out, sample_rgba_array)
    assert out is not sample_rgba_array


def test_relight_blend_clamped_above_one(sample_rgba_array):
    full = heuristic_relight(sample_rgba_array, RelightOptions(blend=BLEND_MAX))
    over = heuristic_relight(sample_rgba_array, RelightOptions(blend=5.0))
    np.testing.assert_array_equal(full, over)


def test_relight_negative_blend_clamped_to_zero(sample_rgba_array):
    out = heuristic_relight(sample_rgba_array, RelightOptions(blend=-2.0))
    np.testing.assert_array_equal(out, sample_rgba_array)


# ---------------------------------------------------------------------------
# Boundary clamping inside relight
# ---------------------------------------------------------------------------


def test_relight_intensity_above_max_clamped(sample_rgba_array):
    inside = heuristic_relight(
        sample_rgba_array, RelightOptions(intensity=INTENSITY_MAX),
    )
    over = heuristic_relight(
        sample_rgba_array, RelightOptions(intensity=INTENSITY_MAX + 5.0),
    )
    np.testing.assert_array_equal(inside, over)


def test_relight_temperature_below_min_clamped(sample_rgba_array):
    inside = heuristic_relight(
        sample_rgba_array, RelightOptions(temperature=TEMPERATURE_MIN),
    )
    under = heuristic_relight(
        sample_rgba_array, RelightOptions(temperature=TEMPERATURE_MIN - 50),
    )
    np.testing.assert_array_equal(inside, under)


def test_relight_temperature_above_max_clamped(sample_rgba_array):
    inside = heuristic_relight(
        sample_rgba_array, RelightOptions(temperature=TEMPERATURE_MAX),
    )
    over = heuristic_relight(
        sample_rgba_array, RelightOptions(temperature=TEMPERATURE_MAX + 50),
    )
    np.testing.assert_array_equal(inside, over)


# ---------------------------------------------------------------------------
# Direction effect — light from opposite side produces different output
# ---------------------------------------------------------------------------


def test_relight_direction_changes_output(sample_rgba_array):
    left = heuristic_relight(
        sample_rgba_array, RelightOptions(azimuth=0, elevation=0, intensity=1.5),
    )
    right = heuristic_relight(
        sample_rgba_array, RelightOptions(azimuth=180, elevation=0, intensity=1.5),
    )
    # Opposite-direction lighting must produce *some* difference.
    diff = np.abs(left.astype(np.int16) - right.astype(np.int16)).sum()
    assert diff > 0


def test_relight_zero_intensity_zero_temperature_returns_close_to_original(
    sample_rgba_array,
):
    out = heuristic_relight(
        sample_rgba_array,
        RelightOptions(intensity=0.0, temperature=0, blend=1.0),
    )
    # Round-trip through float32 / uint8 may shift by 1 LSB occasionally,
    # but the result must be near-identical RGB-wise.
    diff = np.abs(out[..., :3].astype(np.int16)
                  - sample_rgba_array[..., :3].astype(np.int16))
    assert diff.max() <= 1
