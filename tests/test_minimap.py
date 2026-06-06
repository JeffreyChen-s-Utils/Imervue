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
        x, y, w, h = minimap_geometry(1000, 800, 100, 0)
        assert w > 0 and h > 0


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
