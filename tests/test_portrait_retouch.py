"""Tests for the portrait auto-retouch passes."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.portrait_retouch import (
    RetouchOptions,
    auto_retouch,
    fix_red_eye,
    sharpen_region,
    smooth_skin,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# auto_retouch dispatch
# ---------------------------------------------------------------------------


def test_auto_retouch_zero_intensity_is_identity():
    base = _solid(16, 16, (180, 130, 100))  # warm skin tone
    out = auto_retouch(base, RetouchOptions(
        skin_smooth=0.0, red_eye=0.0, eye_sharpen=0.0,
    ))
    assert np.array_equal(out, base)


def test_auto_retouch_default_changes_skin_pixels():
    """A noisy skin-tone image should change after smoothing, even without
    red-eye or sharpen passes."""
    base = _solid(32, 32, (200, 150, 120))  # skin tone seed
    rng = np.random.default_rng(5)
    base[..., :3] = np.clip(
        base[..., :3].astype(np.int16)
        + rng.integers(-20, 20, base[..., :3].shape),
        0, 255,
    ).astype(np.uint8)
    out = auto_retouch(base, RetouchOptions(
        skin_smooth=1.0, skin_radius=4, red_eye=0.0, eye_sharpen=0.0,
    ))
    assert not np.array_equal(out, base)


def test_auto_retouch_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        auto_retouch(arr)


# ---------------------------------------------------------------------------
# smooth_skin
# ---------------------------------------------------------------------------


def test_smooth_skin_zero_intensity_is_identity():
    base = _solid(8, 8, (200, 150, 120))
    out = smooth_skin(base, 0.0)
    assert np.array_equal(out, base)


def test_smooth_skin_only_touches_skin_pixels():
    """A pure-blue input should be unchanged because no pixel passes the
    skin-tone heuristic."""
    base = _solid(16, 16, (10, 10, 200))
    out = smooth_skin(base, 1.0, radius=2)
    assert np.array_equal(out, base)


def test_smooth_skin_preserves_alpha():
    base = _solid(8, 8, (200, 150, 120))
    base[..., 3] = 100
    out = smooth_skin(base, 1.0)
    assert (out[..., 3] == 100).all()


# ---------------------------------------------------------------------------
# fix_red_eye
# ---------------------------------------------------------------------------


def test_fix_red_eye_zero_intensity_is_identity():
    base = _solid(8, 8, (240, 30, 30))
    out = fix_red_eye(base, 0.0)
    assert np.array_equal(out, base)


def test_fix_red_eye_no_red_pixels_is_identity():
    """An image with no red-dominant pixels passes through untouched."""
    base = _solid(8, 8, (30, 200, 200))
    out = fix_red_eye(base, 1.0)
    assert np.array_equal(out, base)


def test_fix_red_eye_darkens_red_pixels():
    base = _solid(8, 8, (240, 30, 30))
    out = fix_red_eye(base, 1.0)
    assert int(out[0, 0, 0]) < 240


def test_fix_red_eye_preserves_alpha():
    base = _solid(8, 8, (240, 30, 30))
    base[..., 3] = 100
    out = fix_red_eye(base, 1.0)
    assert (out[..., 3] == 100).all()


# ---------------------------------------------------------------------------
# sharpen_region
# ---------------------------------------------------------------------------


def test_sharpen_zero_intensity_is_identity():
    base = _solid(16, 16, (128, 128, 128))
    out = sharpen_region(base, 0.0)
    assert np.array_equal(out, base)


def test_sharpen_amplifies_high_frequency_contrast():
    """A checker pattern should have a wider min/max spread after sharpening."""
    base = np.zeros((16, 16, 4), dtype=np.uint8)
    yy, xx = np.indices((16, 16))
    base[((xx + yy) % 2 == 0), :3] = 200
    base[((xx + yy) % 2 == 1), :3] = 50
    base[..., 3] = 255
    out = sharpen_region(base, 1.0)
    spread_before = base[..., :3].astype(np.int16).max() - base[..., :3].astype(np.int16).min()
    spread_after = out[..., :3].astype(np.int16).max() - out[..., :3].astype(np.int16).min()
    assert spread_after >= spread_before


def test_sharpen_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        sharpen_region(arr, 1.0)
