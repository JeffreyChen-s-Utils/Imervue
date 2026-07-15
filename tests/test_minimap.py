"""Tests for the pure deep-zoom minimap geometry helpers."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.minimap import (
    MINIMAP_MARGIN,
    MINIMAP_MAX_H,
    MINIMAP_MAX_W,
    minimap_geometry,
    point_in_rect,
    recenter_offsets,
    viewport_box_rect,
)


class TestMinimapGeometry:
    def test_landscape_caps_width_and_sits_bottom_right(self):
        x, y, w, h = minimap_geometry(1000, 800, 1600, 900)
        assert w == MINIMAP_MAX_W
        assert h == int(MINIMAP_MAX_W / (1600 / 900))
        # Bottom-right with margin.
        assert x == 1000 - w - MINIMAP_MARGIN
        assert y == 800 - h - MINIMAP_MARGIN

    def test_portrait_caps_height(self):
        _, _, w, h = minimap_geometry(1000, 800, 900, 1600)
        assert h == MINIMAP_MAX_H
        # Width derived from height keeps it within the box.
        assert w <= MINIMAP_MAX_W

    def test_zero_height_does_not_divide_by_zero(self):
        # Degenerate image height is clamped, not crashed.
        _, _, w, h = minimap_geometry(1000, 800, 100, 0)
        assert w > 0 and h > 0

    def test_extreme_aspect_keeps_nonzero_dimensions(self):
        # A 10x10000 strip would derive a 0-width minimap (invisible, and a zero
        # divisor in the draw math) — floor it to a thin but real rectangle.
        _, _, w, h = minimap_geometry(1000, 800, 10, 10000)
        assert w >= 1 and h >= 1


class TestViewportBoxRect:
    def test_box_bounded_by_content_height_not_full_canvas(self):
        # 1000x1000 image, 100x100 minimap at origin, zoom 1, no pan. Content
        # height 848 (152 band) → the box bottom is 848/1000 of the strip, not
        # the full height, so it doesn't claim the band-hidden rows are visible.
        x0, y0, x1, y1 = viewport_box_rect((0, 0, 100, 100), 1000, 1000,
                                           0.0, 0.0, 1.0, 1000, 848)
        assert (x0, y0) == pytest.approx((0, 0))
        assert x1 == pytest.approx(100)      # full width visible
        assert y1 == pytest.approx(84.8)     # 848/1000 * 100

    def test_box_guards_degenerate_zoom_and_image(self):
        # Zero zoom / zero image dims must not raise (guarded divisors).
        assert viewport_box_rect((0, 0, 50, 50), 0, 0, 0.0, 0.0, 0.0, 100, 80)


class TestPointInRect:
    def test_inside_and_on_edges(self):
        rect = (10, 20, 100, 50)
        assert point_in_rect(10, 20, rect)      # top-left corner
        assert point_in_rect(60, 45, rect)      # centre
        assert point_in_rect(110, 70, rect)     # bottom-right corner

    @pytest.mark.parametrize("px,py", [(9, 45), (111, 45), (60, 19), (60, 71)])
    def test_outside(self, px, py):
        assert not point_in_rect(px, py, (10, 20, 100, 50))


class TestRecenterOffsets:
    def test_center_click_centers_image_center(self):
        rect = (0, 0, 100, 100)
        # Click the middle of the minimap on a 1000x1000 image at zoom 1 in a
        # 500x500 viewport → image centre (500,500) lands at viewport centre.
        off_x, off_y = recenter_offsets(50, 50, rect, 1000, 1000, 500, 500, 1.0)
        assert off_x == pytest.approx(500 / 2 - 500 * 1.0)
        assert off_y == pytest.approx(500 / 2 - 500 * 1.0)

    def test_top_left_click_maps_to_origin(self):
        rect = (0, 0, 100, 100)
        off_x, off_y = recenter_offsets(0, 0, rect, 1000, 1000, 400, 300, 2.0)
        # Image point (0,0) → centred: offset = view/2 - 0.
        assert off_x == pytest.approx(200)
        assert off_y == pytest.approx(150)

    def test_click_outside_is_clamped(self):
        rect = (0, 0, 100, 100)
        # A click past the right/bottom edge clamps to the far image corner,
        # never beyond it.
        off_x, off_y = recenter_offsets(999, 999, rect, 1000, 1000, 500, 500, 1.0)
        clamped = recenter_offsets(100, 100, rect, 1000, 1000, 500, 500, 1.0)
        assert (off_x, off_y) == clamped
