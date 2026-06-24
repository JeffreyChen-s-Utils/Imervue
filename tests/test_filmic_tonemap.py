"""Tests for the filmic tone-mapping operator."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.filmic_tonemap import HABLE, REINHARD, apply_filmic_tonemap

_LUMA = np.array([0.299, 0.587, 0.114])
_RGBA = 4


def _grey(value, alpha=255, size=(4, 4)):
    arr = np.full((size[0], size[1], _RGBA), value, dtype=np.uint8)
    arr[..., 3] = alpha
    return arr


def _luma(pixel):
    return float(np.dot(pixel[:3], _LUMA))


def test_gradient_stays_monotonic():
    ramp = np.linspace(0, 255, 32, dtype=np.uint8)
    arr = np.zeros((1, 32, _RGBA), dtype=np.uint8)
    arr[..., 0] = arr[..., 1] = arr[..., 2] = ramp
    arr[..., 3] = 255
    out_luma = apply_filmic_tonemap(arr)[..., :3].astype(float) @ _LUMA
    # A monotone input ramp must map to a non-decreasing output ramp.
    assert np.all(np.diff(out_luma[0]) >= -1e-6)


def test_highlights_compressed_more_than_shadows():
    dark = apply_filmic_tonemap(_grey(50), mode=REINHARD)
    bright = apply_filmic_tonemap(_grey(220), mode=REINHARD)
    dark_ratio = _luma(dark[0, 0]) / 50
    bright_ratio = _luma(bright[0, 0]) / 220
    assert bright_ratio < dark_ratio


def test_exposure_brightens():
    base = apply_filmic_tonemap(_grey(100), exposure=0.0)
    lifted = apply_filmic_tonemap(_grey(100), exposure=1.0)
    assert _luma(lifted[0, 0]) > _luma(base[0, 0])


def test_saturation_zero_is_greyscale():
    arr = _grey(120)
    arr[..., 0] = 200  # tint
    out = apply_filmic_tonemap(arr, saturation=0.0)
    assert int(out[0, 0, 0]) == int(out[0, 0, 1]) == int(out[0, 0, 2])


def test_contrast_increases_spread():
    dark_in, bright_in = _grey(25), _grey(128)
    flat = _luma(apply_filmic_tonemap(bright_in, contrast=1.0)[0, 0]) - _luma(
        apply_filmic_tonemap(dark_in, contrast=1.0)[0, 0])
    steep = _luma(apply_filmic_tonemap(bright_in, contrast=2.0)[0, 0]) - _luma(
        apply_filmic_tonemap(dark_in, contrast=2.0)[0, 0])
    assert steep > flat


def test_modes_differ():
    arr = _grey(180)
    assert not np.array_equal(
        apply_filmic_tonemap(arr, mode=REINHARD),
        apply_filmic_tonemap(arr, mode=HABLE),
    )


def test_exposure_clamped():
    out = apply_filmic_tonemap(_grey(100), exposure=999.0)
    assert out.dtype == np.uint8
    assert out[..., :3].max() <= 255


def test_preserves_alpha():
    arr = _grey(120, alpha=150)
    out = apply_filmic_tonemap(arr)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_does_not_mutate_input():
    arr = _grey(120)
    before = arr.copy()
    apply_filmic_tonemap(arr, exposure=1.0, contrast=1.5)
    assert np.array_equal(arr, before)


def test_accepts_rgb_without_alpha():
    arr = np.full((4, 4, 3), 120, dtype=np.uint8)
    out = apply_filmic_tonemap(arr)
    assert out.shape == arr.shape


def test_rejects_bad_mode():
    with pytest.raises(ValueError, match="mode must be one of"):
        apply_filmic_tonemap(_grey(120), mode="aces")


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5, 4), dtype=np.float32),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4 uint8"):
        apply_filmic_tonemap(bad)
