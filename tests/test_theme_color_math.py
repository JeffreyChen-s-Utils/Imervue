"""Tests for WCAG theme colour maths."""
from __future__ import annotations

import pytest

from Imervue.system.theme_color_math import (
    best_foreground,
    contrast_ratio,
    meets_wcag,
    relative_luminance,
    scale_brightness,
)

_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)


# ---------------------------------------------------------------------------
# relative_luminance
# ---------------------------------------------------------------------------


def test_luminance_endpoints():
    assert relative_luminance(_BLACK) == pytest.approx(0.0)
    assert relative_luminance(_WHITE) == pytest.approx(1.0)


def test_luminance_green_brighter_than_blue():
    assert relative_luminance((0, 255, 0)) > relative_luminance((0, 0, 255))


# ---------------------------------------------------------------------------
# contrast_ratio
# ---------------------------------------------------------------------------


def test_contrast_black_white_is_max():
    assert contrast_ratio(_WHITE, _BLACK) == pytest.approx(21.0)


def test_contrast_is_symmetric():
    assert contrast_ratio(_WHITE, _BLACK) == pytest.approx(contrast_ratio(_BLACK, _WHITE))


def test_contrast_identical_is_one():
    assert contrast_ratio((120, 80, 40), (120, 80, 40)) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# meets_wcag
# ---------------------------------------------------------------------------


def test_meets_wcag_pass_and_fail():
    assert meets_wcag(_BLACK, _WHITE) is True
    assert meets_wcag((150, 150, 150), _WHITE) is False


def test_meets_wcag_large_text_is_more_lenient():
    mid = (127, 127, 127)  # contrast ~4.0 on white: in [3.0, 4.5)
    # A pairing that fails AA-normal can pass AA-large (lower threshold).
    assert meets_wcag(mid, _WHITE, level="AA", large_text=False) is False
    assert meets_wcag(mid, _WHITE, level="AA", large_text=True) is True


def test_meets_wcag_aaa_stricter_than_aa():
    grey = (100, 100, 100)  # contrast ~5.9 on white: in [4.5, 7.0)
    assert meets_wcag(grey, _WHITE, level="AA") is True
    assert meets_wcag(grey, _WHITE, level="AAA") is False


def test_meets_wcag_unknown_level_raises():
    with pytest.raises(ValueError, match="AA"):
        meets_wcag(_BLACK, _WHITE, level="AAAA")


# ---------------------------------------------------------------------------
# best_foreground
# ---------------------------------------------------------------------------


def test_best_foreground_picks_readable():
    assert best_foreground(_WHITE) == _BLACK
    assert best_foreground(_BLACK) == _WHITE
    assert best_foreground((20, 20, 20)) == _WHITE


# ---------------------------------------------------------------------------
# scale_brightness
# ---------------------------------------------------------------------------


def test_scale_brightness_lightens_and_darkens():
    assert scale_brightness((100, 100, 100), 1.5) == (150, 150, 150)
    assert scale_brightness((100, 100, 100), 0.5) == (50, 50, 50)


def test_scale_brightness_clamps():
    assert scale_brightness((200, 200, 200), 2.0) == (255, 255, 255)
    assert scale_brightness((100, 100, 100), -1.0) == (0, 0, 0)
