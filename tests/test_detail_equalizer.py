"""Tests for the multi-scale detail equalizer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.detail_equalizer import apply_detail_equalizer, detail_delta

_RGBA = 4


def _noise(h=16, w=16, seed=0):
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, _RGBA), dtype=np.uint8)
    arr[..., :3] = rng.integers(60, 200, (h, w, 3), dtype=np.uint8)
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# detail_delta
# ---------------------------------------------------------------------------


def test_delta_is_zero_for_neutral_gains():
    lum = np.random.default_rng(0).random((12, 12)).astype(np.float32) * 255
    delta = detail_delta(lum, (1.0, 1.0, 1.0))
    assert np.allclose(delta, 0.0, atol=1e-3)


def test_delta_nonzero_when_boosting():
    lum = np.random.default_rng(1).random((12, 12)).astype(np.float32) * 255
    delta = detail_delta(lum, (3.0, 1.0))
    assert np.abs(delta).max() > 0.0


# ---------------------------------------------------------------------------
# apply_detail_equalizer
# ---------------------------------------------------------------------------


def test_neutral_gains_is_identity():
    arr = _noise()
    assert np.array_equal(apply_detail_equalizer(arr, (1.0, 1.0, 1.0)), arr)


def test_boosting_fine_band_raises_contrast():
    arr = _noise()
    out = apply_detail_equalizer(arr, (3.0, 1.0))
    assert np.var(out[..., :3].astype(float)) > np.var(arr[..., :3].astype(float))


def test_removing_fine_band_lowers_contrast():
    arr = _noise()
    out = apply_detail_equalizer(arr, (0.0, 1.0))
    assert np.var(out[..., :3].astype(float)) < np.var(arr[..., :3].astype(float))


def test_single_band_works():
    arr = _noise()
    out = apply_detail_equalizer(arr, (2.0,))
    assert out.shape == arr.shape


def test_gain_clamped():
    arr = _noise()
    out = apply_detail_equalizer(arr, (999.0, 1.0))
    assert out.dtype == np.uint8


def test_preserves_alpha():
    arr = _noise()
    arr[..., 3] = 140
    out = apply_detail_equalizer(arr, (2.0, 1.0))
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_does_not_mutate_input():
    arr = _noise()
    before = arr.copy()
    apply_detail_equalizer(arr, (2.0, 0.5))
    assert np.array_equal(arr, before)


def test_accepts_rgb_without_alpha():
    arr = np.random.default_rng(4).integers(60, 200, (12, 12, 3), dtype=np.uint8)
    out = apply_detail_equalizer(arr, (2.0, 1.0))
    assert out.shape == arr.shape


def test_rejects_empty_band_gains():
    with pytest.raises(ValueError, match="at least one band"):
        apply_detail_equalizer(_noise(), ())


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5, 4), dtype=np.float32),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4 uint8"):
        apply_detail_equalizer(bad, (2.0,))
