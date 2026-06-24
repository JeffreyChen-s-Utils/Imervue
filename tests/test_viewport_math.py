"""Tests for viewport screen <-> image coordinate maths (pure, no Qt)."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.viewport_math import (
    image_to_screen_point,
    screen_to_image_point,
    visible_image_rect,
)


# ---------------------------------------------------------------------------
# point transforms
# ---------------------------------------------------------------------------


def test_screen_to_image_at_offset_is_origin():
    assert screen_to_image_point((10.0, 20.0), (10.0, 20.0), zoom=2.0) == (0.0, 0.0)


def test_image_origin_maps_to_offset():
    assert image_to_screen_point((0.0, 0.0), (10.0, 20.0), zoom=2.0) == (10.0, 20.0)


def test_known_transform():
    assert image_to_screen_point((5.0, 5.0), (10.0, 20.0), 2.0) == (20.0, 30.0)
    assert screen_to_image_point((20.0, 30.0), (10.0, 20.0), 2.0) == (5.0, 5.0)


@pytest.mark.parametrize("point", [(0.0, 0.0), (3.5, 9.0), (123.0, 4.0)])
def test_round_trip(point):
    offset, zoom = (12.0, -7.0), 1.75
    screen = image_to_screen_point(point, offset, zoom)
    back = screen_to_image_point(screen, offset, zoom)
    assert back == pytest.approx(point)


def test_zoom_zero_maps_to_origin():
    assert screen_to_image_point((50.0, 50.0), (0.0, 0.0), zoom=0.0) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# visible_image_rect
# ---------------------------------------------------------------------------


def test_visible_rect_clamps_to_image_bounds():
    # 100x100 viewport over a 50x50 image at 1x, no pan: sees the whole image.
    assert visible_image_rect((100, 100), (50, 50), (0.0, 0.0), 1.0) == (
        0.0, 0.0, 50.0, 50.0)


def test_visible_rect_with_pan():
    # offset (-20,-20) scrolls the image so the top-left 20px is off-screen.
    assert visible_image_rect((40, 40), (100, 100), (-20.0, -20.0), 1.0) == (
        20.0, 20.0, 60.0, 60.0)


def test_visible_rect_with_zoom():
    # At 2x, a 100px viewport spans 50 image px.
    assert visible_image_rect((100, 100), (200, 200), (0.0, 0.0), 2.0) == (
        0.0, 0.0, 50.0, 50.0)


def test_visible_rect_zoom_zero_is_empty():
    assert visible_image_rect((100, 100), (50, 50), (0.0, 0.0), 0.0) == (
        0.0, 0.0, 0.0, 0.0)
