"""Tests for the hover-HUD and loupe placement maths.

Pure arithmetic (no Qt, no GL), so these run on headless CI.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.hud_geometry import (
    clamp_loupe_magnification,
    loupe_source_rect,
    place_hud_box,
    visible_pixel_bounds,
)


def test_place_hud_box_default_to_right():
    hx, hy = place_hud_box(100, 100, 20, 80, 60, view_w=800, view_h=600)
    assert hx == 100 + 20 + 12
    assert hy == 100


def test_place_hud_box_flips_left_when_overflow_right():
    hx, _ = place_hud_box(780, 100, 20, 80, 60, view_w=800, view_h=600)
    assert hx == 780 - 80 - 12


def test_place_hud_box_clamps_bottom_overflow():
    _, hy = place_hud_box(100, 580, 20, 80, 60, view_w=800, view_h=600)
    assert hy == 600 - 60 - 4


def test_place_hud_box_never_negative_y():
    _, hy = place_hud_box(0, 0, 0, 80, 10000, view_w=800, view_h=600)
    assert hy == 0


def test_visible_pixel_bounds_clamped_to_image():
    x0, y0, x1, y1 = visible_pixel_bounds(
        zoom=1.0, off_x=0.0, off_y=0.0,
        view_w=100, view_h=100, img_w=50, img_h=40,
    )
    assert (x0, y0) == (0, 0)
    assert x1 == 50
    assert y1 == 40


def test_visible_pixel_bounds_with_pan_offset():
    # Panned so the top-left of the viewport sits at image pixel (10, 5).
    x0, y0, x1, y1 = visible_pixel_bounds(
        zoom=2.0, off_x=-20.0, off_y=-10.0,
        view_w=40, view_h=40, img_w=1000, img_h=1000,
    )
    assert (x0, y0) == (10, 5)
    assert x1 == pytest.approx(31, abs=1)
    assert y1 == pytest.approx(26, abs=1)


class TestLoupeSourceRect:
    def test_centred_crop_well_inside(self):
        assert loupe_source_rect(100, 100, 40, 40, 1000, 1000) == (80, 80, 120, 120)

    def test_clamps_at_left_edge(self):
        assert loupe_source_rect(5, 100, 40, 40, 1000, 1000) == (0, 80, 40, 120)

    def test_clamps_at_right_edge(self):
        assert loupe_source_rect(995, 100, 40, 40, 1000, 1000) == (960, 80, 1000, 120)

    def test_image_smaller_than_sample(self):
        assert loupe_source_rect(5, 5, 40, 40, 20, 20) == (0, 0, 20, 20)


class TestClampLoupeMagnification:
    def test_scroll_up_magnifies_more(self):
        assert clamp_loupe_magnification(4, 120) == 5

    def test_scroll_down_magnifies_less(self):
        assert clamp_loupe_magnification(4, -120) == 3

    def test_clamps_at_max(self):
        assert clamp_loupe_magnification(16, 120) == 16

    def test_clamps_at_min(self):
        assert clamp_loupe_magnification(2, -120) == 2
