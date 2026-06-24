"""Tests for the shared reverse-map resampling helpers."""
from __future__ import annotations

import numpy as np

from Imervue.image.resample import ensure_rgba, sample_bilinear


def test_ensure_rgba_appends_opaque_alpha():
    rgb = np.full((3, 4, 3), 100, dtype=np.uint8)
    out = ensure_rgba(rgb)
    assert out.shape == (3, 4, 4)
    assert np.all(out[..., 3] == 255)
    assert np.array_equal(out[..., :3], rgb)


def test_ensure_rgba_passes_through_rgba():
    rgba = np.full((3, 4, 4), 50, dtype=np.uint8)
    assert ensure_rgba(rgba) is rgba


def test_sample_identity_coords_returns_source():
    rgba = np.random.default_rng(0).integers(0, 255, (5, 6, 4), dtype=np.uint8)
    yy, xx = np.mgrid[0:5, 0:6].astype(np.float64)
    out = sample_bilinear(rgba, xx, yy)
    assert np.array_equal(out, rgba)


def test_sample_clamps_out_of_bounds():
    rgba = np.arange(4 * 4 * 4, dtype=np.uint8).reshape(4, 4, 4)
    out = sample_bilinear(rgba, np.full((4, 4), -10.0), np.full((4, 4), 99.0))
    # Far out-of-range samples clamp to the bottom-left corner pixel.
    assert np.array_equal(out[0, 0], rgba[3, 0])


def test_sample_interpolates_midpoint():
    rgba = np.zeros((1, 2, 4), dtype=np.uint8)
    rgba[0, 0] = 0
    rgba[0, 1] = 100
    out = sample_bilinear(rgba, np.array([[0.5]]), np.array([[0.0]]))
    assert int(out[0, 0, 0]) == 50
