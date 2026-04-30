"""Tests for auto color correction helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.auto_correct import (
    auto_color,
    auto_contrast,
    auto_levels,
)


def _low_contrast_grey():
    """Image with R, G, B all in [80, 160] — low-contrast grey ramp."""
    img = np.zeros((4, 80, 4), dtype=np.uint8)
    img[..., 3] = 255
    for x in range(80):
        v = 80 + x
        img[:, x, :3] = v
    return img


def _color_cast_image():
    """Image with strong red bias — R mean ≈ 200, G mean ≈ 100, B mean ≈ 50."""
    img = np.zeros((10, 10, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[..., 0] = 200
    img[..., 1] = 100
    img[..., 2] = 50
    return img


# ---------------------------------------------------------------------------
# auto_levels
# ---------------------------------------------------------------------------


def test_auto_levels_stretches_to_full_range():
    img = _low_contrast_grey()
    out = auto_levels(img)
    # After stretching, the darkest pixel should be near 0 and the
    # brightest near 255 in every channel.
    for ch in range(3):
        assert int(out[..., ch].min()) <= 5
        assert int(out[..., ch].max()) >= 250


def test_auto_levels_zero_range_is_noop():
    """A solid-colour image has cmin == cmax — should leave it alone."""
    img = np.full((4, 4, 4), 100, dtype=np.uint8)
    img[..., 3] = 255
    out = auto_levels(img)
    np.testing.assert_array_equal(out, img)


def test_auto_levels_preserves_alpha():
    img = _low_contrast_grey()
    img[..., 3] = 200
    out = auto_levels(img)
    assert (out[..., 3] == 200).all()


def test_auto_levels_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        auto_levels(rgb)


def test_auto_levels_does_not_mutate_input():
    img = _low_contrast_grey()
    snapshot = img.copy()
    auto_levels(img)
    np.testing.assert_array_equal(img, snapshot)


# ---------------------------------------------------------------------------
# auto_contrast
# ---------------------------------------------------------------------------


def test_auto_contrast_expands_luminance_range():
    img = _low_contrast_grey()
    rgb = img[..., :3].astype(np.float32)
    lum_before = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    out = auto_contrast(img)
    rgb_after = out[..., :3].astype(np.float32)
    lum_after = (
        0.299 * rgb_after[..., 0]
        + 0.587 * rgb_after[..., 1]
        + 0.114 * rgb_after[..., 2]
    )
    # The post-correction luminance range covers more of [0, 255].
    assert (lum_after.max() - lum_after.min()) > (lum_before.max() - lum_before.min())


def test_auto_contrast_zero_range_is_noop():
    img = np.full((4, 4, 4), 50, dtype=np.uint8)
    img[..., 3] = 255
    out = auto_contrast(img)
    np.testing.assert_array_equal(out, img)


def test_auto_contrast_preserves_color_ratios():
    """Auto-contrast scales all channels uniformly; the channel
    differences expand (image gets more contrast) when the input
    didn't span the full range."""
    img = np.zeros((1, 4, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[0, 0] = (60, 90, 120, 255)
    img[0, 3] = (160, 180, 200, 255)
    img[0, 1] = (100, 130, 160, 255)
    img[0, 2] = (80, 110, 140, 255)
    out = auto_contrast(img)
    # The two endpoint pixels' luminance difference should grow —
    # luminance(160,180,200) − luminance(60,90,120) ≈ 92 before, 255 after.
    rgb_pre = img[..., :3].astype(np.float32)
    rgb_post = out[..., :3].astype(np.float32)
    weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    lum_pre = (rgb_pre @ weights)[0]
    lum_post = (rgb_post @ weights)[0]
    pre_range = float(lum_pre.max() - lum_pre.min())
    post_range = float(lum_post.max() - lum_post.min())
    assert post_range > pre_range


def test_auto_contrast_preserves_alpha():
    img = _low_contrast_grey()
    img[..., 3] = 100
    out = auto_contrast(img)
    assert (out[..., 3] == 100).all()


def test_auto_contrast_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        auto_contrast(rgb)


# ---------------------------------------------------------------------------
# auto_color
# ---------------------------------------------------------------------------


def test_auto_color_shifts_mean_toward_128():
    img = _color_cast_image()
    out = auto_color(img)
    for ch in range(3):
        mean = float(out[..., ch].mean())
        # Each channel's mean should be near 128 after correction.
        assert abs(mean - 128.0) < 5.0


def test_auto_color_no_change_for_balanced_image():
    """An image whose channels already average to 128 stays put."""
    img = np.full((10, 10, 4), 128, dtype=np.uint8)
    img[..., 3] = 255
    out = auto_color(img)
    np.testing.assert_array_equal(out, img)


def test_auto_color_preserves_alpha():
    img = _color_cast_image()
    img[..., 3] = 200
    out = auto_color(img)
    assert (out[..., 3] == 200).all()


def test_auto_color_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        auto_color(rgb)


def test_auto_color_clamps_overshoot():
    """A channel whose mean is 50 needs +78 shift; a pixel originally
    at 200 in that channel would land at 278 — clamps to 255 instead
    of overflowing."""
    img = np.zeros((10, 10, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[..., 0] = 50
    img[0, 0, 0] = 200
    out = auto_color(img)
    # Bright pixel clamps at 255.
    assert int(out[0, 0, 0]) == 255
