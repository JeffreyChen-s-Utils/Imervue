"""Tests for the film-negative inversion."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.film_negative import apply_film_negative, estimate_film_base

_RGBA = 4


def _img(pixels, alpha=255):
    arr = np.array(pixels, dtype=np.uint8)
    if arr.shape[-1] == _RGB:
        rgba = np.dstack([arr, np.full(arr.shape[:2], alpha, dtype=np.uint8)])
        return rgba
    return arr


_RGB = 3


# ---------------------------------------------------------------------------
# estimate_film_base
# ---------------------------------------------------------------------------


def test_estimate_returns_three_positive_channels():
    arr = np.random.default_rng(0).integers(10, 250, (8, 8, 4), dtype=np.uint8)
    base = estimate_film_base(arr)
    assert len(base) == _RGB
    assert all(c > 0.0 for c in base)


def test_estimate_tracks_bright_point():
    arr = np.zeros((8, 8, 4), dtype=np.uint8)
    arr[..., 0] = 200  # red brightest
    arr[..., 1] = 100
    arr[..., 2] = 50
    arr[..., 3] = 255
    base = estimate_film_base(arr)
    assert base[0] > base[1] > base[2]


# ---------------------------------------------------------------------------
# apply_film_negative
# ---------------------------------------------------------------------------


def test_uniform_negative_maps_to_white():
    arr = np.full((4, 4, 4), 128, dtype=np.uint8)
    arr[..., 3] = 255
    out = apply_film_negative(arr)
    assert np.ptp(out[..., :3]) == 0
    assert int(out[0, 0, 0]) == 255


def test_inversion_flips_bright_and_dark():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[:, :2, :3] = 200  # bright negative (=> dark positive)
    arr[:, 2:, :3] = 50   # dark negative   (=> bright positive)
    arr[..., 3] = 255
    base = (200 / 255, 200 / 255, 200 / 255)
    out = apply_film_negative(arr, film_base=base, gamma=1.0)
    assert int(out[0, 0, 0]) < int(out[0, 3, 0])
    assert int(out[0, 0, 0]) == pytest.approx(64, abs=3)
    assert int(out[0, 3, 0]) == 255


def test_film_base_balances_colour_cast():
    # An orange-cast uniform negative + matching base => neutral positive.
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = 200, 150, 100
    arr[..., 3] = 255
    out = apply_film_negative(arr, film_base=(200 / 255, 150 / 255, 100 / 255))
    assert int(out[0, 0, 0]) == int(out[0, 0, 1]) == int(out[0, 0, 2])


def test_gamma_brightens_midtones():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[:, :2, :3] = 200
    arr[:, 2:, :3] = 50
    arr[..., 3] = 255
    base = (200 / 255, 200 / 255, 200 / 255)
    dark = int(apply_film_negative(arr, film_base=base, gamma=1.0)[0, 0, 0])
    brighter = int(apply_film_negative(arr, film_base=base, gamma=2.0)[0, 0, 0])
    assert brighter > dark


def test_gamma_clamped():
    arr = np.full((4, 4, 4), 100, dtype=np.uint8)
    arr[..., 3] = 255
    out = apply_film_negative(arr, gamma=999.0)
    assert out.dtype == np.uint8


def test_preserves_alpha():
    arr = np.full((4, 4, 4), 100, dtype=np.uint8)
    arr[..., 3] = 130
    out = apply_film_negative(arr)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_does_not_mutate_input():
    arr = np.full((4, 4, 4), 100, dtype=np.uint8)
    arr[..., 3] = 255
    before = arr.copy()
    apply_film_negative(arr)
    assert np.array_equal(arr, before)


def test_accepts_rgb_without_alpha():
    arr = np.full((4, 4, 3), 100, dtype=np.uint8)
    out = apply_film_negative(arr)
    assert out.shape == arr.shape


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5, 4), dtype=np.float32),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4 uint8"):
        apply_film_negative(bad)
