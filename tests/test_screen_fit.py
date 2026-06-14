"""Tests for screen_fit — proportional window rescale between screens.

Pure-Python tuple math; no Qt needed.
"""
from __future__ import annotations

import pytest

from Imervue.gui.screen_fit import clamp_rect_into, rescale_rect_between_screens

_FHD = (0, 0, 1920, 1080)
_UHD = (0, 0, 3840, 2160)
_SMALL = (0, 0, 1280, 720)
# Secondary monitor positioned to the right of a 1920-wide primary.
_SECONDARY = (1920, 0, 1280, 1024)


def _is_inside(rect, bounds):
    x, y, w, h = rect
    bx, by, bw, bh = bounds
    return x >= bx and y >= by and x + w <= bx + bw and y + h <= by + bh


class TestClampRectInto:
    def test_rect_already_inside_is_unchanged(self):
        assert clamp_rect_into((100, 100, 800, 600), _FHD) == (100, 100, 800, 600)

    def test_oversized_rect_shrinks_to_bounds(self):
        assert clamp_rect_into((0, 0, 5000, 5000), _FHD) == (0, 0, 1920, 1080)

    def test_offscreen_rect_shifts_back_in(self):
        # Hanging off the bottom-right corner → pushed up-left.
        assert clamp_rect_into((1800, 1000, 400, 300), _FHD) == (1520, 780, 400, 300)

    def test_negative_origin_clamps_to_bounds_origin(self):
        assert clamp_rect_into((-50, -50, 400, 300), _FHD) == (0, 0, 400, 300)

    def test_respects_offset_bounds(self):
        # Bounds that don't start at (0, 0) — e.g. a secondary monitor.
        assert clamp_rect_into((0, 0, 400, 300), _SECONDARY) == (1920, 0, 400, 300)


class TestRescaleRectBetweenScreens:
    def test_same_screen_is_identity(self):
        window = (100, 100, 800, 600)
        assert rescale_rect_between_screens(window, _FHD, _FHD) == window

    def test_bigger_screen_scales_up_proportionally(self):
        # Half-screen window stays a half-screen window.
        window = (0, 0, 960, 540)
        assert rescale_rect_between_screens(window, _FHD, _UHD) == (0, 0, 1920, 1080)

    def test_smaller_screen_scales_down_and_fits(self):
        window = (100, 100, 1600, 900)
        result = rescale_rect_between_screens(window, _FHD, _SMALL)
        assert result[2] == pytest.approx(1600 / 1920 * 1280, abs=1)
        assert result[3] == pytest.approx(900 / 1080 * 720, abs=1)
        assert _is_inside(result, _SMALL)

    def test_relative_centre_is_preserved(self):
        # Window centred at 25% / 50% of the old screen lands at the same
        # fractions on the new one.
        window = (240, 270, 480, 540)  # centre (480, 540) = (25%, 50%)
        x, y, w, h = rescale_rect_between_screens(window, _FHD, _UHD)
        assert x + w / 2 == pytest.approx(0.25 * 3840, abs=1)
        assert y + h / 2 == pytest.approx(0.50 * 2160, abs=1)

    def test_window_larger_than_old_screen_caps_at_full_new_screen(self):
        window = (0, 0, 4000, 3000)
        assert rescale_rect_between_screens(window, _FHD, _SMALL) == _SMALL

    def test_offset_target_screen_lands_inside_it(self):
        window = (100, 100, 800, 600)
        result = rescale_rect_between_screens(window, _FHD, _SECONDARY)
        assert _is_inside(result, _SECONDARY)

    def test_degenerate_old_screen_falls_back_to_clamp(self):
        window = (5000, 5000, 800, 600)
        result = rescale_rect_between_screens(window, (0, 0, 0, 0), _FHD)
        assert result == (1120, 480, 800, 600)
        assert _is_inside(result, _FHD)

    def test_zero_height_old_screen_falls_back_to_clamp(self):
        result = rescale_rect_between_screens((10, 10, 100, 100), (0, 0, 1920, 0), _FHD)
        assert result == (10, 10, 100, 100)

    def test_result_always_inside_new_screen(self):
        # Window hanging half off the old screen must still land fully
        # inside the new one after the rescale.
        window = (1800, 900, 800, 600)
        result = rescale_rect_between_screens(window, _FHD, _SMALL)
        assert _is_inside(result, _SMALL)

    def test_tiny_window_never_collapses_to_zero(self):
        result = rescale_rect_between_screens((0, 0, 1, 1), _UHD, _SMALL)
        assert result[2] >= 1 and result[3] >= 1
