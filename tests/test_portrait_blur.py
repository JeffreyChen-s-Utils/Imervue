"""Tests for the portrait-mode blur compositor."""
from __future__ import annotations

import numpy as np
import pytest

from portrait_mode.portrait_blur import (
    BLUR_RADIUS_MAX,
    BLUR_RADIUS_MIN,
    PortraitBlurOptions,
    apply_portrait_blur,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


def _checker(h, w, square=4):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    yy, xx = np.indices((h, w))
    mask = ((xx // square) + (yy // square)) % 2 == 0
    arr[mask, 0] = 255
    arr[mask, 1] = 255
    arr[mask, 2] = 255
    arr[..., 3] = 255
    return arr


def test_full_subject_mask_returns_input_unchanged():
    """When the mask is 255 everywhere, the output equals the input."""
    arr = _checker(32, 32, square=4)
    mask = np.full((32, 32), 255, dtype=np.uint8)
    out = apply_portrait_blur(arr, mask, PortraitBlurOptions(blur_radius=8))
    assert np.array_equal(out, arr)


def test_no_subject_mask_blurs_entire_image():
    """When the mask is 0 everywhere, the output is fully blurred."""
    arr = _checker(32, 32, square=4)
    mask = np.zeros((32, 32), dtype=np.uint8)
    out = apply_portrait_blur(
        arr, mask, PortraitBlurOptions(blur_radius=8, feather_radius=0),
    )
    # A fully blurred checkerboard should have visibly less variance
    assert out[..., :3].std() < arr[..., :3].std()


def test_subject_region_stays_sharp():
    """A 1-shaped mask should leave the subject column pixel-accurate."""
    arr = _checker(32, 32, square=4)
    mask = np.zeros((32, 32), dtype=np.uint8)
    mask[:, 10:14] = 255
    out = apply_portrait_blur(
        arr, mask, PortraitBlurOptions(blur_radius=8, feather_radius=0),
    )
    # The subject column should match the input exactly
    assert np.array_equal(out[:, 10:14, :3], arr[:, 10:14, :3])


def test_alpha_channel_preserved():
    arr = _solid(8, 8, (100, 100, 100))
    arr[..., 3] = 80
    mask = np.zeros((8, 8), dtype=np.uint8)
    out = apply_portrait_blur(arr, mask, PortraitBlurOptions())
    assert (out[..., 3] == 80).all()


def test_blur_radius_clamped():
    arr = _solid(8, 8, (100, 100, 100))
    mask = np.zeros((8, 8), dtype=np.uint8)
    # Above the cap should not raise
    out = apply_portrait_blur(
        arr, mask, PortraitBlurOptions(blur_radius=BLUR_RADIUS_MAX + 50),
    )
    assert out.shape == arr.shape


def test_blur_radius_min_clamps_up():
    arr = _solid(8, 8, (100, 100, 100))
    mask = np.zeros((8, 8), dtype=np.uint8)
    # Below the floor should not raise either
    out = apply_portrait_blur(
        arr, mask, PortraitBlurOptions(blur_radius=BLUR_RADIUS_MIN - 100),
    )
    assert out.shape == arr.shape


def test_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    mask = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_portrait_blur(arr, mask, PortraitBlurOptions())


def test_rejects_mismatched_mask_shape():
    arr = _solid(4, 4, (100, 100, 100))
    mask = np.zeros((8, 8), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_portrait_blur(arr, mask, PortraitBlurOptions())


def test_rejects_3d_mask():
    arr = _solid(4, 4, (100, 100, 100))
    mask = np.zeros((4, 4, 1), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_portrait_blur(arr, mask, PortraitBlurOptions())


def test_feather_softens_edge():
    """A feathered mask should produce a gradient between sharp and blurred."""
    arr = _checker(64, 64, square=4)
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[:, :32] = 255
    out_no_feather = apply_portrait_blur(
        arr, mask, PortraitBlurOptions(blur_radius=8, feather_radius=0),
    )
    out_feathered = apply_portrait_blur(
        arr, mask, PortraitBlurOptions(blur_radius=8, feather_radius=8),
    )
    # The pixel at the seam should differ between the two results
    assert not np.array_equal(out_no_feather[:, 30:34, :3],
                              out_feathered[:, 30:34, :3])
