"""Tests for the kaleidoscope filter."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.kaleidoscope import fold_angle, kaleidoscope

_TWO_PI = 2.0 * np.pi


# ---------------------------------------------------------------------------
# fold_angle
# ---------------------------------------------------------------------------


def test_fold_within_wedge_unchanged():
    seg = _TWO_PI / 4
    theta = np.array([0.0, 0.2, seg / 2 - 0.01])
    assert np.allclose(fold_angle(theta, 4, 0.0), theta)


def test_fold_mirrors_beyond_half_wedge():
    seg = _TWO_PI / 4
    inside = fold_angle(np.array([seg / 2 - 0.1]), 4, 0.0)
    beyond = fold_angle(np.array([seg / 2 + 0.1]), 4, 0.0)
    # A point just past the half-line mirrors onto its reflection inside.
    assert beyond[0] == pytest.approx(inside[0], abs=1e-6)


def test_fold_is_periodic_per_segment():
    seg = _TWO_PI / 6
    theta = np.array([0.3])
    assert fold_angle(theta, 6, 0.0)[0] == pytest.approx(
        fold_angle(theta + seg, 6, 0.0)[0], abs=1e-6,
    )


def test_fold_respects_offset():
    offset = 0.5
    # With the offset, angles just above it pass through the base wedge untouched.
    theta = np.array([offset + 0.1])
    assert fold_angle(theta, 4, offset)[0] == pytest.approx(theta[0], abs=1e-6)


# ---------------------------------------------------------------------------
# kaleidoscope
# ---------------------------------------------------------------------------


def test_returns_rgba_same_shape():
    arr = np.random.default_rng(0).integers(0, 255, (12, 12, 4), dtype=np.uint8)
    out = kaleidoscope(arr, segments=6)
    assert out.shape == (12, 12, 4)


def test_promotes_rgb_to_rgba():
    rgb = np.full((10, 10, 3), 100, dtype=np.uint8)
    assert kaleidoscope(rgb, segments=4).shape == (10, 10, 4)


def test_uniform_image_stays_uniform():
    arr = np.full((10, 10, 4), 77, dtype=np.uint8)
    arr[..., 3] = 255
    out = kaleidoscope(arr, segments=5)
    assert np.ptp(out[..., 0]) == 0


def test_custom_center_runs():
    arr = np.random.default_rng(1).integers(0, 255, (10, 10, 4), dtype=np.uint8)
    out = kaleidoscope(arr, segments=4, center=(2.0, 3.0))
    assert out.shape == (10, 10, 4)


def test_deterministic():
    arr = np.random.default_rng(2).integers(0, 255, (10, 10, 4), dtype=np.uint8)
    assert np.array_equal(kaleidoscope(arr, 6), kaleidoscope(arr, 6))


def test_does_not_mutate_input():
    arr = np.random.default_rng(3).integers(0, 255, (10, 10, 4), dtype=np.uint8)
    before = arr.copy()
    kaleidoscope(arr, segments=6)
    assert np.array_equal(arr, before)


def test_rejects_too_few_segments():
    arr = np.zeros((6, 6, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="segments must be"):
        kaleidoscope(arr, segments=1)


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4"):
        kaleidoscope(bad)
