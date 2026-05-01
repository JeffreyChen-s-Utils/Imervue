"""Tests for the Curves tone-mapping filter."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.curves import (
    CURVE_CHANNELS,
    IDENTITY_POINTS,
    CurveOptions,
    apply_curves,
    build_lut,
    compress_highlights_preset,
    lift_shadows_preset,
    s_curve_preset,
)


# ---------------------------------------------------------------------------
# build_lut
# ---------------------------------------------------------------------------


def test_identity_curve_returns_identity_lut():
    lut = build_lut(IDENTITY_POINTS)
    assert lut.dtype == np.uint8
    assert lut.shape == (256,)
    np.testing.assert_array_equal(lut, np.arange(256, dtype=np.uint8))


def test_lut_interpolates_linearly_between_points():
    """A curve from (0,0) to (255,255) via (128, 200) lifts midtones."""
    lut = build_lut([(0, 0), (128, 200), (255, 255)])
    assert int(lut[0]) == 0
    assert int(lut[128]) == 200
    assert int(lut[255]) == 255
    # A pixel between 0 and 128 must lift above identity.
    assert int(lut[64]) > 64


def test_lut_clamps_out_of_range_input_x():
    """Negative x or >255 x must not crash; the value is clamped first
    so the LUT still has 256 entries in [0, 255]."""
    lut = build_lut([(-100, 50), (300, 200)])
    assert lut.shape == (256,)
    assert lut.min() >= 0
    assert lut.max() <= 255


def test_lut_clamps_out_of_range_y():
    lut = build_lut([(0, -50), (255, 400)])
    assert lut.min() >= 0
    assert lut.max() <= 255


def test_lut_handles_duplicate_x_keeps_last():
    """Two points with the same input x must produce the LAST entry's
    output — matches 'drag onto existing point' UI semantics."""
    lut = build_lut([(0, 0), (128, 50), (128, 200), (255, 255)])
    assert int(lut[128]) == 200


def test_lut_with_no_valid_points_falls_back_to_identity():
    lut = build_lut([])
    np.testing.assert_array_equal(lut, np.arange(256, dtype=np.uint8))


def test_lut_with_garbage_entries_still_works():
    """Non-2-tuple entries get filtered before interpolation."""
    lut = build_lut([(0, 0), "garbage", None, (1, 2, 3), (255, 255)])
    assert lut.shape == (256,)


# ---------------------------------------------------------------------------
# apply_curves — RGBA shape + identity short-circuit
# ---------------------------------------------------------------------------


@pytest.fixture
def gray_canvas():
    arr = np.full((16, 16, 4), 128, dtype=np.uint8)
    arr[..., 3] = 255
    return arr


def test_disabled_returns_input_unchanged(gray_canvas):
    options = CurveOptions(enabled=False)
    out = apply_curves(gray_canvas, options)
    assert out is gray_canvas


def test_identity_curves_short_circuit(gray_canvas):
    """Enabled but every channel is identity — the source array is
    returned unchanged so the recipe pipeline pays nothing."""
    options = CurveOptions(
        enabled=True,
        per_channel={ch: IDENTITY_POINTS for ch in CURVE_CHANNELS},
    )
    out = apply_curves(gray_canvas, options)
    assert out is gray_canvas


def test_apply_curves_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_curves(bad, CurveOptions(enabled=True))


def test_apply_curves_does_not_mutate_input(gray_canvas):
    options = CurveOptions(
        enabled=True,
        per_channel={**{ch: IDENTITY_POINTS for ch in CURVE_CHANNELS},
                     "rgb": s_curve_preset(0.3)},
    )
    snapshot = gray_canvas.copy()
    apply_curves(gray_canvas, options)
    np.testing.assert_array_equal(gray_canvas, snapshot)


def test_apply_curves_preserves_alpha(gray_canvas):
    """Alpha must not be touched even when an aggressive RGB curve runs."""
    gray_canvas[..., 3] = 200
    options = CurveOptions(
        enabled=True,
        per_channel={**{ch: IDENTITY_POINTS for ch in CURVE_CHANNELS},
                     "rgb": s_curve_preset(0.4)},
    )
    out = apply_curves(gray_canvas, options)
    assert (out[..., 3] == 200).all()


# ---------------------------------------------------------------------------
# Per-channel layering
# ---------------------------------------------------------------------------


def test_master_curve_remaps_all_channels(gray_canvas):
    """A non-identity master curve must change every RGB channel."""
    options = CurveOptions(
        enabled=True,
        per_channel={**{ch: IDENTITY_POINTS for ch in CURVE_CHANNELS},
                     "rgb": [(0, 0), (128, 200), (255, 255)]},
    )
    out = apply_curves(gray_canvas, options)
    # Source is grey 128 → master curve at 128 returns 200.
    assert int(out[0, 0, 0]) == 200
    assert int(out[0, 0, 1]) == 200
    assert int(out[0, 0, 2]) == 200


def test_per_channel_curve_only_affects_its_channel(gray_canvas):
    options = CurveOptions(
        enabled=True,
        per_channel={**{ch: IDENTITY_POINTS for ch in CURVE_CHANNELS},
                     "r": [(0, 0), (128, 50), (255, 255)]},
    )
    out = apply_curves(gray_canvas, options)
    # R is pulled down, G/B stay at 128.
    assert int(out[0, 0, 0]) == 50
    assert int(out[0, 0, 1]) == 128
    assert int(out[0, 0, 2]) == 128


def test_master_then_per_channel_apply_in_order(gray_canvas):
    """Master maps 128→200, then per-R maps 200→100.
    Final R must be 100."""
    options = CurveOptions(
        enabled=True,
        per_channel={
            **{ch: IDENTITY_POINTS for ch in CURVE_CHANNELS},
            "rgb": [(0, 0), (128, 200), (255, 255)],
            "r": [(0, 0), (200, 100), (255, 255)],
        },
    )
    out = apply_curves(gray_canvas, options)
    assert int(out[0, 0, 0]) == 100   # R after both curves
    assert int(out[0, 0, 1]) == 200   # G after master only
    assert int(out[0, 0, 2]) == 200


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


def test_s_curve_increases_contrast():
    """Apply S-curve to a midtone-flat canvas; pixels above 128 get
    brighter, pixels below 128 get darker."""
    canvas = np.zeros((1, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[0, 0, :3] = 64
    canvas[0, 1, :3] = 128
    canvas[0, 2, :3] = 192
    canvas[0, 3, :3] = 255
    options = CurveOptions(
        enabled=True,
        per_channel={**{ch: IDENTITY_POINTS for ch in CURVE_CHANNELS},
                     "rgb": s_curve_preset(0.3)},
    )
    out = apply_curves(canvas, options)
    assert int(out[0, 0, 0]) <= 64        # shadow pulled down
    assert int(out[0, 2, 0]) >= 192       # highlight pushed up


def test_s_curve_zero_strength_is_identity():
    points = s_curve_preset(0.0)
    lut = build_lut(points)
    np.testing.assert_array_equal(lut, np.arange(256, dtype=np.uint8))


def test_lift_shadows_brightens_low_inputs():
    points = lift_shadows_preset(0.2)
    lut = build_lut(points)
    # A black pixel (0) must lift above 0 with a non-zero amount.
    assert int(lut[0]) > 0
    # White must stay white.
    assert int(lut[255]) == 255


def test_compress_highlights_pulls_white_down():
    points = compress_highlights_preset(0.3)
    lut = build_lut(points)
    assert int(lut[255]) < 255
    assert int(lut[0]) == 0


@pytest.mark.parametrize("preset_fn", [
    s_curve_preset, lift_shadows_preset, compress_highlights_preset,
])
def test_presets_clamp_extreme_strength(preset_fn):
    """Way-out-of-range strength must not crash; result is still
    a sensible curve (every y in [0, 255])."""
    points = preset_fn(99.0)
    for _x, y in points:
        assert 0 <= y <= 255


# ---------------------------------------------------------------------------
# CurveOptions round-trip
# ---------------------------------------------------------------------------


def test_curve_options_roundtrip_preserves_per_channel():
    options = CurveOptions(
        enabled=True,
        per_channel={
            "rgb": s_curve_preset(0.2),
            "r": ((0, 0), (128, 100), (255, 255)),
            "g": IDENTITY_POINTS,
            "b": ((0, 30), (255, 255)),
        },
    )
    raw = options.to_dict()
    rebuilt = CurveOptions.from_dict(raw)
    assert rebuilt.enabled is True
    # Each channel survives the trip; padding may add the (0,..) /
    # (255,..) endpoints but the user-set values are preserved.
    rgb_xs = [p[0] for p in rebuilt.per_channel["rgb"]]
    assert 0 in rgb_xs and 255 in rgb_xs
    assert rebuilt.per_channel["g"] == IDENTITY_POINTS


def test_from_dict_with_garbage_falls_back_to_identity():
    out = CurveOptions.from_dict("not a dict")
    assert out.enabled is False
    for ch in CURVE_CHANNELS:
        assert out.per_channel[ch] == IDENTITY_POINTS


def test_from_dict_with_missing_channel_keeps_identity():
    raw = {"enabled": True, "per_channel": {"r": [[0, 0], [255, 255]]}}
    out = CurveOptions.from_dict(raw)
    # g, b, rgb absent → identity.
    assert out.per_channel["g"] == IDENTITY_POINTS
    assert out.per_channel["b"] == IDENTITY_POINTS
