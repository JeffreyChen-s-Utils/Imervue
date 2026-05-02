"""Tests for HSL + Gradient Map adjustments added in 15b."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.adjustments import (
    ADJUSTMENT_KINDS,
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


def test_registry_includes_new_kinds():
    assert "hsl" in ADJUSTMENT_KINDS
    assert "gradient_map" in ADJUSTMENT_KINDS


# ---------------------------------------------------------------------------
# HSL
# ---------------------------------------------------------------------------


def test_hsl_identity_preserves_pixels():
    img = _solid((128, 64, 200))
    out = apply_adjustment(img, Adjustment(kind="hsl"))
    np.testing.assert_allclose(out[..., :3], img[..., :3], atol=1)


def test_hsl_180_degree_hue_shift_inverts_red_to_cyan():
    img = _solid((255, 0, 0))
    out = apply_adjustment(
        img,
        Adjustment(kind="hsl", params={"hue_shift_deg": 180.0}),
    )
    assert int(out[0, 0, 0]) <= 5
    assert int(out[0, 0, 1]) >= 250
    assert int(out[0, 0, 2]) >= 250


def test_hsl_zero_saturation_yields_grayscale():
    img = _solid((200, 100, 50))
    out = apply_adjustment(
        img,
        Adjustment(kind="hsl", params={"saturation": 0.0}),
    )
    r, g, b = int(out[0, 0, 0]), int(out[0, 0, 1]), int(out[0, 0, 2])
    assert abs(r - g) <= 1
    assert abs(g - b) <= 1


def test_hsl_lightness_zero_yields_black():
    """In HSL, L=0 is pure black regardless of saturation."""
    img = _solid((255, 0, 0))   # vivid red
    out = apply_adjustment(
        img, Adjustment(kind="hsl", params={"lightness": 0.0}),
    )
    assert (out[..., :3] == 0).all()


def test_hsl_lightness_two_over_pure_color_drives_to_white():
    """Doubling lightness on a pure mid-grey moves it toward white."""
    img = _solid((128, 128, 128))
    out = apply_adjustment(
        img, Adjustment(kind="hsl", params={"lightness": 2.0}),
    )
    assert int(out[0, 0, 0]) >= 250


def test_hsl_alpha_unchanged():
    img = _solid((100, 100, 100))
    img[..., 3] = 150
    out = apply_adjustment(
        img, Adjustment(kind="hsl", params={"hue_shift_deg": 90.0}),
    )
    assert (out[..., 3] == 150).all()


# ---------------------------------------------------------------------------
# Gradient Map
# ---------------------------------------------------------------------------


def test_gradient_map_default_produces_grayscale():
    """Default stops are black→white, so a colour image becomes
    luminance-based grayscale."""
    img = _solid((200, 100, 50))
    out = apply_adjustment(img, Adjustment(kind="gradient_map"))
    r, g, b = int(out[0, 0, 0]), int(out[0, 0, 1]), int(out[0, 0, 2])
    assert abs(r - g) <= 2
    assert abs(g - b) <= 2


def test_gradient_map_two_stop_warm():
    """Map shadows to red, highlights to yellow — interpolates."""
    img = _solid((128, 128, 128))   # mid-luminance ≈ 128
    out = apply_adjustment(img, Adjustment(
        kind="gradient_map",
        params={"stops": [
            {"position": 0.0, "color": [255, 0, 0, 255]},
            {"position": 1.0, "color": [255, 255, 0, 255]},
        ]},
    ))
    # Mid-tone maps to mid-gradient = (255, 128, 0) approx.
    r, g = int(out[0, 0, 0]), int(out[0, 0, 1])
    assert r > 240   # both stops have R = 255
    assert 100 < g < 160   # interpolated mid


def test_gradient_map_pure_black_takes_first_stop():
    img = _solid((0, 0, 0))
    out = apply_adjustment(img, Adjustment(
        kind="gradient_map",
        params={"stops": [
            {"position": 0.0, "color": [255, 0, 0, 255]},
            {"position": 1.0, "color": [0, 0, 255, 255]},
        ]},
    ))
    assert tuple(out[0, 0, :3]) == (255, 0, 0)


def test_gradient_map_pure_white_takes_last_stop():
    img = _solid((255, 255, 255))
    out = apply_adjustment(img, Adjustment(
        kind="gradient_map",
        params={"stops": [
            {"position": 0.0, "color": [255, 0, 0, 255]},
            {"position": 1.0, "color": [0, 0, 255, 255]},
        ]},
    ))
    assert tuple(out[0, 0, :3]) == (0, 0, 255)


def test_gradient_map_rgb_only_color_stop_padded_to_alpha_255():
    """Color stops with 3-tuple RGB get padded to alpha 255 instead
    of crashing the adjustment."""
    img = _solid((128, 128, 128))
    out = apply_adjustment(img, Adjustment(
        kind="gradient_map",
        params={"stops": [
            {"position": 0.0, "color": [0, 0, 0]},      # 3-tuple
            {"position": 1.0, "color": [255, 255, 255]},  # 3-tuple
        ]},
    ))
    # Should produce mid-gray (~128, 128, 128).
    assert abs(int(out[0, 0, 0]) - 128) <= 2


def test_gradient_map_corrupt_stops_fall_back_to_default():
    """If every supplied stop is bad, the helper falls through to the
    black→white default rather than crashing."""
    img = _solid((128, 128, 128))
    out = apply_adjustment(img, Adjustment(
        kind="gradient_map",
        params={"stops": ["garbage", {"position": "x"}, 42]},
    ))
    # Default is grayscale ramp — output ≈ luminance.
    assert abs(int(out[0, 0, 0]) - 128) <= 2


def test_gradient_map_alpha_unchanged():
    img = _solid((128, 128, 128))
    img[..., 3] = 200
    out = apply_adjustment(img, Adjustment(kind="gradient_map"))
    assert (out[..., 3] == 200).all()


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind,params", [
    ("hsl", {"hue_shift_deg": 30.0, "saturation": 0.5, "lightness": 1.2}),
    ("gradient_map", {"stops": [
        {"position": 0.0, "color": [255, 0, 0, 255]},
        {"position": 1.0, "color": [0, 0, 255, 255]},
    ]}),
])
def test_round_trip_via_dict(kind, params):
    a = Adjustment(kind=kind, params=params)
    rebuilt = Adjustment.from_dict(a.to_dict())
    for key, value in params.items():
        assert rebuilt.params[key] == value
