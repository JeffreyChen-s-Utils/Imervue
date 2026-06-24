"""Tests for the velvia luminance-weighted saturation boost."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.velvia import apply_velvia

_RGBA = 4


def _solid(rgb, alpha=255, size=(4, 4)):
    arr = np.zeros((size[0], size[1], _RGBA), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = alpha
    return arr


def _saturation(pixel):
    mx, mn = int(max(pixel)), int(min(pixel))
    return (mx - mn) / max(mx, 1)


def test_strength_zero_is_identity():
    arr = _solid((180, 120, 90))
    assert np.array_equal(apply_velvia(arr, strength=0.0), arr)


def test_grey_pixel_unchanged():
    # A neutral pixel has no colour to push away from its grey -> identity.
    arr = _solid((128, 128, 128))
    out = apply_velvia(arr, strength=2.0)
    assert np.array_equal(out[..., :3], arr[..., :3])


def test_boost_increases_saturation():
    arr = _solid((170, 130, 120))
    out = apply_velvia(arr, strength=2.0, luminance_protection=0.0)
    assert _saturation(out[0, 0, :3]) > _saturation(arr[0, 0, :3])


def test_muted_colour_boosted_more_than_saturated():
    muted = _solid((160, 140, 135))    # low saturation
    vivid = _solid((220, 40, 30))      # high saturation
    muted_gain = _saturation(apply_velvia(muted, 2.0, 0.0)[0, 0, :3]) - _saturation(muted[0, 0, :3])
    vivid_gain = _saturation(apply_velvia(vivid, 2.0, 0.0)[0, 0, :3]) - _saturation(vivid[0, 0, :3])
    assert muted_gain > vivid_gain


def test_shadow_protection_limits_dark_pixels():
    dark = _solid((40, 28, 24))
    bright = _solid((220, 170, 150))
    dark_gain = _saturation(apply_velvia(dark, 2.0, 1.0)[0, 0, :3]) - _saturation(dark[0, 0, :3])
    bright_gain = _saturation(apply_velvia(bright, 2.0, 1.0)[0, 0, :3]) - _saturation(bright[0, 0, :3])
    assert dark_gain < bright_gain


def test_negative_strength_desaturates():
    arr = _solid((200, 90, 60))
    out = apply_velvia(arr, strength=-1.0, luminance_protection=0.0)
    assert _saturation(out[0, 0, :3]) < _saturation(arr[0, 0, :3])


def test_strength_clamped():
    arr = _solid((170, 130, 120))
    # Absurd strength must clamp, not overflow.
    out = apply_velvia(arr, strength=999.0)
    assert out.dtype == np.uint8
    assert out[..., :3].max() <= 255


def test_preserves_alpha():
    arr = _solid((200, 90, 60), alpha=150)
    out = apply_velvia(arr, strength=2.0)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_does_not_mutate_input():
    arr = _solid((200, 90, 60))
    before = arr.copy()
    apply_velvia(arr, strength=2.0)
    assert np.array_equal(arr, before)


def test_accepts_rgb_without_alpha():
    arr = np.full((4, 4, 3), 100, dtype=np.uint8)
    arr[..., 0] = 180
    out = apply_velvia(arr, strength=1.0)
    assert out.shape == arr.shape


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5, 4), dtype=np.float32),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4 uint8"):
        apply_velvia(bad)
