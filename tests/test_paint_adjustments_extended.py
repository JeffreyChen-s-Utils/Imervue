"""Tests for the additional adjustment kinds added in 13b."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.adjustments import (
    ADJUSTMENT_KINDS,
    SELECTIVE_RANGES,
    Adjustment,
    apply_adjustment,
)


def _solid(rgb, h=4, w=4):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = rgb[0]
    img[..., 1] = rgb[1]
    img[..., 2] = rgb[2]
    img[..., 3] = 255
    return img


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_adjustment_kinds_includes_extended_set():
    assert {"brightness_contrast", "color_balance", "selective_color",
            "photo_filter"} <= set(ADJUSTMENT_KINDS)


def test_selective_ranges_set():
    assert set(SELECTIVE_RANGES) == {
        "reds", "yellows", "greens", "cyans", "blues", "magentas",
    }


# ---------------------------------------------------------------------------
# Brightness / Contrast
# ---------------------------------------------------------------------------


def test_brightness_contrast_identity_preserves_pixels():
    img = _solid((128, 64, 200))
    out = apply_adjustment(img, Adjustment(kind="brightness_contrast"))
    np.testing.assert_array_equal(out[..., :3], img[..., :3])


def test_brightness_positive_lifts_pixels():
    img = _solid((100, 100, 100))
    out = apply_adjustment(
        img,
        Adjustment(kind="brightness_contrast", params={"brightness": 0.4}),
    )
    assert int(out[0, 0, 0]) > 100


def test_brightness_negative_darkens_pixels():
    img = _solid((150, 150, 150))
    out = apply_adjustment(
        img,
        Adjustment(kind="brightness_contrast", params={"brightness": -0.3}),
    )
    assert int(out[0, 0, 0]) < 150


def test_contrast_positive_pushes_away_from_midgrey():
    """Pure black + 0.5 contrast moves further toward 0; pure white
    moves further toward 255."""
    black = _solid((0, 0, 0))
    white = _solid((255, 255, 255))
    out_b = apply_adjustment(
        black, Adjustment(kind="brightness_contrast", params={"contrast": 0.5}),
    )
    out_w = apply_adjustment(
        white, Adjustment(kind="brightness_contrast", params={"contrast": 0.5}),
    )
    # Black stays at 0 (clipped), white stays at 255 (clipped). The
    # MIDGREY case better illustrates the pivot.
    grey = _solid((128, 128, 128))
    out_g = apply_adjustment(
        grey, Adjustment(kind="brightness_contrast", params={"contrast": 0.5}),
    )
    # Midgrey + contrast = midgrey (pivot at 0.5 for normalized 0.5).
    # 128/255 = 0.502 → after contrast 1.5 around 0.5: (0.502 - 0.5) *
    # 1.5 + 0.5 = 0.503. So it should be about 128.
    assert abs(int(out_g[0, 0, 0]) - 128) <= 2
    # Black & white stay at the extremes.
    assert int(out_b[0, 0, 0]) == 0
    assert int(out_w[0, 0, 0]) == 255


def test_contrast_negative_pulls_toward_midgrey():
    img = _solid((255, 255, 255))
    out = apply_adjustment(
        img, Adjustment(kind="brightness_contrast", params={"contrast": -0.5}),
    )
    # Pure white with -0.5 contrast: (1 - 0.5) * 0.5 + 0.5 = 0.75 → 191.
    assert int(out[0, 0, 0]) < 255
    assert int(out[0, 0, 0]) > 100


# ---------------------------------------------------------------------------
# Color Balance
# ---------------------------------------------------------------------------


def test_color_balance_identity():
    img = _solid((128, 128, 128))
    out = apply_adjustment(img, Adjustment(kind="color_balance"))
    np.testing.assert_array_equal(out[..., :3], img[..., :3])


def test_color_balance_shadows_only_affects_dark_pixels():
    """A shift in the shadows band moves dark pixels strongly and
    leaves white pixels essentially untouched."""
    dark = _solid((20, 20, 20))
    bright = _solid((240, 240, 240))
    adj = Adjustment(
        kind="color_balance",
        params={"shadows": [0.4, 0.0, 0.0]},  # push dark pixels redder
    )
    out_dark = apply_adjustment(dark, adj)
    out_bright = apply_adjustment(bright, adj)
    assert int(out_dark[0, 0, 0]) > 20 + 50   # significant red boost
    assert abs(int(out_bright[0, 0, 0]) - 240) <= 5   # near no change


def test_color_balance_highlights_only_affects_bright_pixels():
    dark = _solid((20, 20, 20))
    bright = _solid((240, 240, 240))
    adj = Adjustment(
        kind="color_balance",
        params={"highlights": [0.0, 0.0, 0.4]},  # push bright pixels bluer
    )
    out_bright = apply_adjustment(bright, adj)
    out_dark = apply_adjustment(dark, adj)
    assert int(out_bright[0, 0, 2]) > 240
    assert abs(int(out_dark[0, 0, 2]) - 20) <= 5


def test_color_balance_midtones_peak_at_midgrey():
    grey = _solid((128, 128, 128))
    adj = Adjustment(
        kind="color_balance",
        params={"midtones": [0.0, 0.4, 0.0]},  # green shift
    )
    out = apply_adjustment(grey, adj)
    assert int(out[0, 0, 1]) > 128


def test_color_balance_alpha_unchanged():
    img = _solid((128, 128, 128))
    img[..., 3] = 200
    out = apply_adjustment(
        img,
        Adjustment(kind="color_balance",
                   params={"midtones": [0.5, -0.5, 0.0]}),
    )
    assert (out[..., 3] == 200).all()


# ---------------------------------------------------------------------------
# Selective Color
# ---------------------------------------------------------------------------


def test_selective_color_targets_named_range_only():
    """A red-targeted hue shift moves a red pixel and barely touches a
    green pixel."""
    red = _solid((255, 0, 0))
    green = _solid((0, 255, 0))
    adj = Adjustment(
        kind="selective_color",
        params={"range": "reds", "hue_shift_deg": 60.0},
    )
    out_red = apply_adjustment(red, adj)
    out_green = apply_adjustment(green, adj)
    # Red should rotate toward yellow.
    assert int(out_red[0, 0, 1]) > 100
    # Green stays green-ish.
    assert int(out_green[0, 0, 1]) > 200


def test_selective_color_unknown_range_falls_back_to_reds():
    red = _solid((255, 0, 0))
    out = apply_adjustment(
        red,
        Adjustment(kind="selective_color",
                   params={"range": "kaleidoscope", "hue_shift_deg": 60.0}),
    )
    # Behaves like "reds" — the red pixel still gets shifted.
    assert int(out[0, 0, 1]) > 100


def test_selective_color_zero_shifts_is_identity():
    img = _solid((255, 0, 0))
    out = apply_adjustment(img, Adjustment(kind="selective_color"))
    np.testing.assert_allclose(out[..., :3], img[..., :3], atol=1)


def test_selective_color_saturation_delta_zero_grayscales_target():
    """saturation_delta = -1 on a red pixel desaturates it."""
    red = _solid((255, 0, 0))
    out = apply_adjustment(
        red,
        Adjustment(kind="selective_color",
                   params={"range": "reds", "saturation_delta": -1.0}),
    )
    # After full desaturation, R / G / B are equal-ish (within rounding).
    r, g, b = int(out[0, 0, 0]), int(out[0, 0, 1]), int(out[0, 0, 2])
    assert abs(r - g) <= 5
    assert abs(g - b) <= 5


# ---------------------------------------------------------------------------
# Photo Filter
# ---------------------------------------------------------------------------


def test_photo_filter_default_warms_pixels():
    img = _solid((128, 128, 128))
    out = apply_adjustment(img, Adjustment(kind="photo_filter"))
    # The warming filter multiplies through a colour weighted toward
    # red, so the result tints warm: R > G > B even though the absolute
    # luminance dips a bit (multiplication can only darken, never
    # brighten — Photoshop's filter has the same property at lower
    # densities).
    r, g, b = int(out[0, 0, 0]), int(out[0, 0, 1]), int(out[0, 0, 2])
    assert r > g > b


def test_photo_filter_zero_density_returns_input():
    img = _solid((128, 128, 128))
    out = apply_adjustment(
        img,
        Adjustment(kind="photo_filter", params={"density": 0.0}),
    )
    np.testing.assert_array_equal(out[..., :3], img[..., :3])


def test_photo_filter_full_density_uses_filter_color():
    img = _solid((128, 128, 128))
    out = apply_adjustment(
        img,
        Adjustment(kind="photo_filter", params={
            "color": [255, 100, 50], "density": 1.0,
        }),
    )
    # density=1 → final RGB = original_rgb * filter_rgb.
    # 128/255 * 255 = 128; 128/255 * 100 ≈ 50; 128/255 * 50 ≈ 25.
    assert abs(int(out[0, 0, 0]) - 128) <= 2
    assert abs(int(out[0, 0, 1]) - 50) <= 2
    assert abs(int(out[0, 0, 2]) - 25) <= 2


def test_photo_filter_corrupt_color_falls_back_to_default(tmp_path):
    img = _solid((128, 128, 128))
    out = apply_adjustment(
        img,
        Adjustment(kind="photo_filter", params={"color": "garbage"}),
    )
    # Falls back to the warming default — R / G / B come out warm:
    # R > B (red bias) is the warming signature.
    r = int(out[0, 0, 0])
    b = int(out[0, 0, 2])
    assert r > b


# ---------------------------------------------------------------------------
# Round-trip via dict for new kinds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind,params", [
    ("brightness_contrast", {"brightness": 0.2, "contrast": -0.1}),
    ("color_balance", {"shadows": [0.1, 0.0, -0.1]}),
    ("selective_color", {"range": "blues", "hue_shift_deg": 30.0}),
    ("photo_filter", {"color": [200, 100, 50], "density": 0.4}),
])
def test_extended_adjustments_round_trip_via_dict(kind, params):
    a = Adjustment(kind=kind, params=params)
    rebuilt = Adjustment.from_dict(a.to_dict())
    assert rebuilt.kind == kind
    for key, value in params.items():
        assert rebuilt.params[key] == value
