"""Tests for perceptual (OkLab / OkLCH) colour mixing."""
from __future__ import annotations

import pytest

from Imervue.image.gradient_perceptual import (
    mix_colors_perceptual,
    oklab_to_oklch,
    oklab_to_rgb,
    oklch_to_oklab,
    rgb_to_oklab,
)

_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)
_BLUE = (0, 0, 255)
_YELLOW = (255, 255, 0)


def _close(a, b, tol=2):
    return all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


def _spread(rgb):
    return max(rgb) - min(rgb)


# ---------------------------------------------------------------------------
# OkLab conversion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rgb", [_BLACK, _WHITE, _BLUE, _YELLOW, (200, 120, 30), (17, 200, 99)])
def test_rgb_oklab_round_trip(rgb):
    assert _close(oklab_to_rgb(rgb_to_oklab(rgb)), rgb)


def test_oklab_lightness_endpoints():
    assert rgb_to_oklab(_BLACK)[0] == pytest.approx(0.0, abs=1e-6)
    assert rgb_to_oklab(_WHITE)[0] == pytest.approx(1.0, abs=1e-3)


def test_oklab_oklch_round_trip():
    lab = rgb_to_oklab((200, 120, 30))
    back = oklch_to_oklab(oklab_to_oklch(lab))
    assert all(abs(a - b) < 1e-9 for a, b in zip(lab, back, strict=True))


def test_oklch_hue_in_range():
    _, _, hue = oklab_to_oklch(rgb_to_oklab(_BLUE))
    assert 0.0 <= hue < 360.0


# ---------------------------------------------------------------------------
# mix_colors_perceptual
# ---------------------------------------------------------------------------


def test_mix_endpoints():
    assert _close(mix_colors_perceptual(_BLUE, _YELLOW, 0.0), _BLUE)
    assert _close(mix_colors_perceptual(_BLUE, _YELLOW, 1.0), _YELLOW)


def test_mix_rgb_mode_is_plain_lerp():
    assert mix_colors_perceptual((0, 0, 0), (100, 200, 40), 0.5, mode="rgb") == (
        50, 100, 20)


def test_perceptual_midpoint_avoids_grey():
    # sRGB midpoint of blue+yellow is neutral grey (zero channel spread);
    # OkLab keeps colour, so its midpoint is not grey.
    rgb_mid = mix_colors_perceptual(_BLUE, _YELLOW, 0.5, mode="rgb")
    oklab_mid = mix_colors_perceptual(_BLUE, _YELLOW, 0.5, mode="oklab")
    assert _spread(rgb_mid) <= 1
    assert _spread(oklab_mid) > 10


def test_mix_clamps_t():
    assert _close(mix_colors_perceptual(_BLUE, _YELLOW, -1.0), _BLUE)
    assert _close(mix_colors_perceptual(_BLUE, _YELLOW, 5.0), _YELLOW)


def test_mix_unknown_mode_raises():
    with pytest.raises(ValueError, match="oklch"):
        mix_colors_perceptual(_BLUE, _YELLOW, 0.5, mode="hsv")
