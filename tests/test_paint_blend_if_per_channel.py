"""Tests for per-RGB-channel blend-if gates added in 17a."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from Imervue.paint.blend_if import (
    BlendIf,
    ChannelRange,
    compute_blend_if_mask,
)


def _solid(rgb, h=4, w=4):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = rgb[0]
    img[..., 1] = rgb[1]
    img[..., 2] = rgb[2]
    img[..., 3] = 255
    return img


# ---------------------------------------------------------------------------
# ChannelRange dataclass
# ---------------------------------------------------------------------------


def test_channel_range_default_full_band():
    r = ChannelRange()
    assert r.lo == 0
    assert r.hi == 255


def test_channel_range_is_frozen():
    r = ChannelRange()
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.lo = 50  # type: ignore[misc]


def test_channel_range_rejects_out_of_range():
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        ChannelRange(lo=300)


def test_channel_range_rejects_negative_feather():
    with pytest.raises(ValueError, match="feather"):
        ChannelRange(lo_feather=-1)


def test_channel_range_rejects_inverted_band():
    with pytest.raises(ValueError, match="empty"):
        ChannelRange(lo=200, hi=100)


def test_channel_range_round_trip_via_dict():
    r = ChannelRange(lo=50, hi=200, lo_feather=5, hi_feather=10)
    rebuilt = ChannelRange.from_dict(r.to_dict())
    assert rebuilt == r


def test_channel_range_from_dict_clamps_corrupt():
    rebuilt = ChannelRange.from_dict({"lo": 999, "hi": -50})
    # 999 → 255, -50 → 0; lo > hi collapses to common value.
    assert 0 <= rebuilt.lo <= rebuilt.hi <= 255


# ---------------------------------------------------------------------------
# Per-channel gates on the layer
# ---------------------------------------------------------------------------


def test_this_red_gate_hides_pixels_outside_red_range():
    """A pixel with red=200 should be hidden by a this_red range
    that excludes red >= 100."""
    img = _solid((200, 50, 50))
    mask = compute_blend_if_mask(
        img, None,
        BlendIf(this_red=ChannelRange(lo=0, hi=99)),
    )
    np.testing.assert_array_equal(mask, np.zeros_like(mask))


def test_this_red_gate_passes_pixels_inside_range():
    img = _solid((50, 200, 100))
    mask = compute_blend_if_mask(
        img, None,
        BlendIf(this_red=ChannelRange(lo=0, hi=100)),
    )
    np.testing.assert_array_equal(mask, np.ones_like(mask))


def test_this_green_gate_independent_of_red():
    """A red gate that passes shouldn't be affected by a green gate
    that also passes — both should pass."""
    img = _solid((50, 50, 50))
    mask = compute_blend_if_mask(
        img, None,
        BlendIf(
            this_red=ChannelRange(lo=0, hi=100),
            this_green=ChannelRange(lo=0, hi=100),
        ),
    )
    np.testing.assert_array_equal(mask, np.ones_like(mask))


def test_per_channel_gates_intersect_with_each_other():
    """If red gate passes but blue gate doesn't, the result is hidden."""
    img = _solid((50, 50, 250))   # blue too high
    mask = compute_blend_if_mask(
        img, None,
        BlendIf(
            this_red=ChannelRange(lo=0, hi=100),     # passes
            this_blue=ChannelRange(lo=0, hi=100),    # fails
        ),
    )
    np.testing.assert_array_equal(mask, np.zeros_like(mask))


def test_per_channel_gate_intersects_with_luminance():
    """Per-channel gate combines with the existing luminance gate via
    AND (multiplicative alpha)."""
    img = _solid((50, 50, 50))   # luminance ≈ 50
    mask = compute_blend_if_mask(
        img, None,
        BlendIf(
            this_min=100,   # luminance gate FAILS (50 < 100)
            this_red=ChannelRange(lo=0, hi=100),   # red gate passes
        ),
    )
    # Final alpha = lum_alpha * red_alpha = 0 * 1 = 0.
    np.testing.assert_array_equal(mask, np.zeros_like(mask))


def test_per_channel_feather_produces_intermediate_alpha():
    """Red channel value just inside the feather band → alpha < 1."""
    img = _solid((90, 50, 50))   # red 90
    mask = compute_blend_if_mask(
        img, None,
        BlendIf(this_red=ChannelRange(lo=100, lo_feather=20)),
    )
    # 90 in [80, 100] feather band → alpha ≈ (90 - 80) / 20 = 0.5.
    assert abs(float(mask[0, 0]) - 0.5) < 0.05


# ---------------------------------------------------------------------------
# Per-channel gates on the underlying composite
# ---------------------------------------------------------------------------


def test_underlying_per_channel_gate_filters_by_underlying_value():
    layer = _solid((128, 128, 128))
    underlying = _solid((50, 200, 50))   # green high
    mask = compute_blend_if_mask(
        layer, underlying,
        BlendIf(underlying_green=ChannelRange(lo=0, hi=100)),
    )
    # Underlying green is 200, gate hi=100 — fails.
    np.testing.assert_array_equal(mask, np.zeros_like(mask))


# ---------------------------------------------------------------------------
# Round-trip via dict for the new fields
# ---------------------------------------------------------------------------


def test_blend_if_round_trip_with_per_channel():
    b = BlendIf(
        this_min=20, this_max=200,
        this_red=ChannelRange(lo=10, hi=240),
        underlying_blue=ChannelRange(lo=50, hi=150, lo_feather=5),
    )
    rebuilt = BlendIf.from_dict(b.to_dict())
    assert rebuilt.this_red == ChannelRange(lo=10, hi=240)
    assert rebuilt.this_green is None
    assert rebuilt.underlying_blue == ChannelRange(lo=50, hi=150, lo_feather=5)


def test_blend_if_round_trip_no_per_channel_keeps_none():
    """A persisted blend_if without any per-channel keys reloads with
    every per-channel slot still None — backward compat with 16e."""
    b = BlendIf(this_min=20, this_max=200)
    rebuilt = BlendIf.from_dict(b.to_dict())
    assert rebuilt.this_red is None
    assert rebuilt.this_green is None
    assert rebuilt.this_blue is None
    assert rebuilt.underlying_red is None


def test_blend_if_from_dict_drops_corrupt_per_channel_value():
    rebuilt = BlendIf.from_dict({
        "this_min": 0, "this_max": 255,
        "this_red": "garbage",
    })
    assert rebuilt.this_red is None


# ---------------------------------------------------------------------------
# Backward-compat with 16e
# ---------------------------------------------------------------------------


def test_existing_luminance_only_blend_if_still_works():
    """A 16e-style BlendIf with no per-channel fields behaves
    exactly as before."""
    img = _solid((20, 20, 20))   # luminance ~20
    mask = compute_blend_if_mask(
        img, None, BlendIf(this_min=100),
    )
    np.testing.assert_array_equal(mask, np.zeros_like(mask))
