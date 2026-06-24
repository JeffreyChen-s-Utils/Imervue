"""Tests for the polar coordinate warp."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.polar import polar_distort


def _gradient(h=16, w=16):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = (np.arange(h)[:, None] * (255 // h)).astype(np.uint8)  # row ramp
    arr[..., 3] = 255
    return arr


def test_returns_rgba_same_shape():
    out = polar_distort(_gradient(), to_polar=True)
    assert out.shape == (16, 16, 4)


def test_promotes_rgb_to_rgba():
    rgb = np.full((8, 8, 3), 120, dtype=np.uint8)
    out = polar_distort(rgb)
    assert out.shape == (8, 8, 4)


def test_uniform_image_stays_uniform_to_polar():
    arr = np.full((10, 10, 4), 90, dtype=np.uint8)
    arr[..., 3] = 255
    out = polar_distort(arr, to_polar=True)
    assert np.ptp(out[..., 0]) == 0


def test_uniform_image_stays_uniform_unroll():
    arr = np.full((10, 10, 4), 90, dtype=np.uint8)
    arr[..., 3] = 255
    out = polar_distort(arr, to_polar=False)
    assert np.ptp(out[..., 0]) == 0


def test_invert_swaps_radial_mapping():
    arr = _gradient()
    normal = polar_distort(arr, to_polar=True, invert=False)
    flipped = polar_distort(arr, to_polar=True, invert=True)
    # The centre samples the top row one way and the bottom row the other.
    cy, cx = 8, 8
    assert abs(int(normal[cy, cx, 0]) - int(flipped[cy, cx, 0])) > 50


def test_does_not_mutate_input():
    arr = _gradient()
    before = arr.copy()
    polar_distort(arr, to_polar=True)
    assert np.array_equal(arr, before)


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4"):
        polar_distort(bad)
