"""Tests for the colour-space helpers used by the paint colour dock."""
from __future__ import annotations

import pytest

from Imervue.paint.color_math import (
    hex_to_rgb,
    hsv_to_rgb,
    rgb_to_hex,
    rgb_to_hsv,
)


# ---------------------------------------------------------------------------
# RGB ↔ HSV
# ---------------------------------------------------------------------------


def test_rgb_to_hsv_pure_red():
    h, s, v = rgb_to_hsv((255, 0, 0))
    assert h == pytest.approx(0.0, abs=0.5)
    assert s == pytest.approx(1.0, abs=1e-3)
    assert v == pytest.approx(1.0, abs=1e-3)


def test_rgb_to_hsv_pure_green():
    h, s, v = rgb_to_hsv((0, 255, 0))
    assert h == pytest.approx(120.0, abs=0.5)
    assert s == pytest.approx(1.0, abs=1e-3)
    assert v == pytest.approx(1.0, abs=1e-3)


def test_rgb_to_hsv_pure_blue():
    h, s, v = rgb_to_hsv((0, 0, 255))
    assert h == pytest.approx(240.0, abs=0.5)
    assert s == pytest.approx(1.0, abs=1e-3)


def test_rgb_to_hsv_white_has_zero_saturation():
    _, s, v = rgb_to_hsv((255, 255, 255))
    assert s == 0.0
    assert v == pytest.approx(1.0, abs=1e-3)


def test_rgb_to_hsv_black_has_zero_value():
    _, _, v = rgb_to_hsv((0, 0, 0))
    assert v == 0.0


def test_rgb_to_hsv_clamps_out_of_range_components():
    _, s, v = rgb_to_hsv((300, -50, 128))
    # 300 → clamped to 255; -50 → 0; 128 stays.
    assert s == pytest.approx(1.0, abs=1e-3)
    assert v == pytest.approx(1.0, abs=1e-3)


def test_hsv_round_trip_through_rgb():
    for original in [(10, 20, 30), (255, 128, 0), (200, 100, 50), (130, 220, 240)]:
        rebuilt = hsv_to_rgb(rgb_to_hsv(original))
        # 1-LSB tolerance — the conversion goes through floats.
        assert all(abs(a - b) <= 1 for a, b in zip(original, rebuilt, strict=True))


def test_hsv_to_rgb_clamps_saturation():
    rgb = hsv_to_rgb((0.0, 5.0, 1.0))  # over-saturated
    assert rgb == (255, 0, 0)


def test_hsv_to_rgb_wraps_hue():
    a = hsv_to_rgb((30.0, 1.0, 1.0))
    b = hsv_to_rgb((30.0 + 360.0, 1.0, 1.0))
    assert a == b


# ---------------------------------------------------------------------------
# Hex helpers
# ---------------------------------------------------------------------------


def test_rgb_to_hex_canonical():
    assert rgb_to_hex((255, 0, 128)) == "#FF0080"


def test_rgb_to_hex_clamps_components():
    assert rgb_to_hex((300, -1, 128)) == "#FF0080"


def test_hex_to_rgb_full_form_with_hash():
    assert hex_to_rgb("#1A2B3C") == (26, 43, 60)


def test_hex_to_rgb_full_form_without_hash():
    assert hex_to_rgb("1A2B3C") == (26, 43, 60)


def test_hex_to_rgb_short_form():
    assert hex_to_rgb("#abc") == (170, 187, 204)


def test_hex_to_rgb_returns_none_on_garbage():
    assert hex_to_rgb("#zzzzzz") is None
    assert hex_to_rgb("not a colour") is None
    assert hex_to_rgb(None) is None
    assert hex_to_rgb("12345") is None


def test_hex_round_trip_via_rgb():
    for rgb in [(0, 0, 0), (255, 255, 255), (1, 2, 3), (200, 50, 7)]:
        assert hex_to_rgb(rgb_to_hex(rgb)) == rgb
