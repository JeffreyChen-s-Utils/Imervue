"""Tests for the Modify canvas fit-scale (never upscale past native size).

``_fit_display_scale`` is a pure function; importing it pulls PySide6 but
constructs no widget and needs no display server.
"""
from __future__ import annotations

import pytest

from Imervue.gui.annotation_canvas import _fit_display_scale


def test_large_image_fits_down_to_the_canvas():
    # 2000-wide image into a 1000-wide canvas → half size.
    assert _fit_display_scale(2000, 1000, 1000, 800) == pytest.approx(0.5)


def test_small_image_is_not_upscaled():
    # Image smaller than the canvas stays at native size (the "too large" fix).
    assert _fit_display_scale(400, 300, 1600, 900) == pytest.approx(1.0)


def test_scale_is_limited_by_the_tighter_axis():
    # Wide-but-short canvas → height is the binding constraint.
    assert _fit_display_scale(1000, 1000, 5000, 500) == pytest.approx(0.5)


def test_exact_fit_is_one():
    assert _fit_display_scale(1000, 800, 1000, 800) == pytest.approx(1.0)


@pytest.mark.parametrize("bw,bh,cw,ch", [
    (0, 100, 100, 100),
    (100, 0, 100, 100),
    (100, 100, 0, 100),
    (100, 100, 100, 0),
])
def test_degenerate_dimensions_return_zero(bw, bh, cw, ch):
    assert _fit_display_scale(bw, bh, cw, ch) == 0.0
