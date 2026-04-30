"""Tests for cross-image colour transfer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.match_color import color_statistics, match_color


def _solid(rgb, h=4, w=4):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., :3] = rgb
    img[..., 3] = 255
    return img


def _gradient(h=8, w=8, axis="x"):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = 255
    for i in range(w if axis == "x" else h):
        v = int(255 * i / max(1, (w if axis == "x" else h) - 1))
        if axis == "x":
            img[:, i, :3] = v
        else:
            img[i, :, :3] = v
    return img


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_match_color_rejects_non_rgba_source():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    ref = _solid((100, 100, 100))
    with pytest.raises(ValueError, match="source"):
        match_color(rgb, ref)


def test_match_color_rejects_non_rgba_reference():
    src = _solid((100, 100, 100))
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="reference"):
        match_color(src, rgb)


# ---------------------------------------------------------------------------
# Basic transfer
# ---------------------------------------------------------------------------


def test_match_color_strength_zero_returns_source():
    src = _solid((100, 100, 100))
    ref = _solid((255, 0, 0))
    out = match_color(src, ref, strength=0.0)
    np.testing.assert_array_equal(out, src)


def test_match_color_warm_reference_warms_source():
    """A neutral grey gradient + a warm reference (high red, low blue)
    should pull the output's blue mean down toward the reference's
    blue mean."""
    src = _gradient()
    ref = np.zeros((8, 8, 4), dtype=np.uint8)
    ref[..., 3] = 255
    # Warm reference: R high, B low, with the same gradient structure
    # so std-dev matches the source.
    for i in range(8):
        v = int(255 * i / 7)
        ref[:, i, 0] = v + 30 if v + 30 <= 255 else 255   # red bias
        ref[:, i, 1] = v // 2
        ref[:, i, 2] = v // 4   # blue starved
    out = match_color(src, ref)
    src_b_mean = float(src[..., 2].mean())
    out_b_mean = float(out[..., 2].mean())
    ref_b_mean = float(ref[..., 2].mean())
    # Output's B mean should track the reference's B mean (low) rather
    # than the source's neutral B mean.
    assert abs(out_b_mean - ref_b_mean) < abs(src_b_mean - ref_b_mean)


def test_match_color_identity_when_source_equals_reference():
    """If source has the same statistics as reference, the output
    should equal the source (within rounding)."""
    src = _gradient()
    ref = src.copy()
    out = match_color(src, ref)
    np.testing.assert_allclose(out, src, atol=1)


def test_match_color_alpha_preserved():
    src = _solid((100, 100, 100))
    src[..., 3] = 200
    ref = _solid((255, 0, 0))
    out = match_color(src, ref)
    assert (out[..., 3] == 200).all()


def test_match_color_strength_partial_lies_between():
    src = _gradient()
    ref = np.zeros((8, 8, 4), dtype=np.uint8)
    ref[..., 3] = 255
    ref[..., 0] = 200   # warm reference
    full = match_color(src, ref, strength=1.0)
    half = match_color(src, ref, strength=0.5)
    # Half-strength R should land between source R and full-strength R.
    src_r = float(src[..., 0].mean())
    full_r = float(full[..., 0].mean())
    half_r = float(half[..., 0].mean())
    lo = min(src_r, full_r)
    hi = max(src_r, full_r)
    assert lo - 1 <= half_r <= hi + 1


def test_match_color_does_not_mutate_inputs():
    src = _solid((100, 100, 100))
    ref = _solid((255, 0, 0))
    src_snapshot = src.copy()
    ref_snapshot = ref.copy()
    match_color(src, ref)
    np.testing.assert_array_equal(src, src_snapshot)
    np.testing.assert_array_equal(ref, ref_snapshot)


def test_match_color_constant_source_safely_offsets():
    """Source with zero standard deviation can't be normalised by std;
    the helper should fall back to a flat offset toward the reference
    mean rather than dividing by zero."""
    src = _solid((128, 128, 128))   # constant — std == 0
    ref = _solid((200, 100, 50))
    out = match_color(src, ref)
    # Output mean should be near reference mean, not exploding.
    assert abs(int(out[0, 0, 0]) - 200) < 5
    assert abs(int(out[0, 0, 1]) - 100) < 5
    assert abs(int(out[0, 0, 2]) - 50) < 5


# ---------------------------------------------------------------------------
# color_statistics
# ---------------------------------------------------------------------------


def test_color_statistics_returns_per_channel_mean_std():
    img = _solid((100, 50, 25))
    stats = color_statistics(img)
    # Solid colour has mean = colour, std = 0.
    assert abs(stats["r"][0] - 100) < 0.1
    assert abs(stats["g"][0] - 50) < 0.1
    assert abs(stats["b"][0] - 25) < 0.1
    assert stats["r"][1] == 0.0


def test_color_statistics_gradient_has_nonzero_std():
    img = _gradient()
    stats = color_statistics(img)
    assert stats["r"][1] > 0


def test_color_statistics_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        color_statistics(rgb)
