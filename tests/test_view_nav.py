"""Tests for the pure deep-zoom view-navigation helpers."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.view_nav import (
    clamp_pan_offset,
    stepped_zoom,
    toggle_zoom_target,
    zoom_about_point,
    zoom_to_region,
)


class TestSteppedZoom:
    def test_zooms_in_by_factor(self):
        assert stepped_zoom(1.0, 1.25, 0.05, 50.0) == pytest.approx(1.25)

    def test_zooms_out_by_factor(self):
        assert stepped_zoom(1.0, 0.8, 0.05, 50.0) == pytest.approx(0.8)

    def test_clamps_to_upper_limit(self):
        assert stepped_zoom(40.0, 2.0, 0.05, 50.0) == pytest.approx(50.0)

    def test_clamps_to_lower_limit(self):
        assert stepped_zoom(0.06, 0.5, 0.05, 50.0) == pytest.approx(0.05)

    def test_at_limit_is_idempotent(self):
        # Already at the cap → stays, so the caller can detect "no change".
        assert stepped_zoom(50.0, 1.25, 0.05, 50.0) == pytest.approx(50.0)


class TestToggleZoomTarget:
    def test_at_actual_size_goes_to_fit(self):
        assert toggle_zoom_target(1.0, 0.4) == pytest.approx(0.4)

    def test_near_actual_size_within_eps_goes_to_fit(self):
        assert toggle_zoom_target(1.0005, 0.4) == pytest.approx(0.4)

    def test_at_fit_goes_to_actual_size(self):
        assert toggle_zoom_target(0.4, 0.4) == pytest.approx(1.0)

    def test_arbitrary_zoom_goes_to_actual_size(self):
        assert toggle_zoom_target(3.0, 0.4) == pytest.approx(1.0)

    def test_small_image_fit_equals_actual_is_stable(self):
        # Image smaller than the canvas → fit is 1.0; toggling stays at 1.0.
        assert toggle_zoom_target(1.0, 1.0) == pytest.approx(1.0)


class TestZoomAboutPoint:
    def test_cursor_point_stays_fixed(self):
        # The image pixel under the cursor must map to the same screen x
        # before and after the zoom.
        offset, cursor, old, new = 50.0, 200.0, 1.0, 2.0
        img_x = (cursor - offset) / old
        new_offset = zoom_about_point(offset, cursor, old, new)
        assert img_x * new + new_offset == pytest.approx(cursor)

    def test_no_zoom_change_keeps_offset(self):
        assert zoom_about_point(50.0, 200.0, 2.0, 2.0) == pytest.approx(50.0)

    def test_zero_old_zoom_is_guarded(self):
        # Degenerate old zoom must not divide by zero; offset is unchanged.
        assert zoom_about_point(50.0, 200.0, 0.0, 2.0) == pytest.approx(50.0)


class TestClampPanOffset:
    def test_smaller_than_canvas_recentres(self):
        # Image narrower than the viewport → snaps to centred, ignoring offset.
        assert clamp_pan_offset(999.0, 100.0, 300.0) == pytest.approx(100.0)

    def test_within_bounds_is_unchanged(self):
        # Image wider than canvas; offset inside [canvas-image, 0] stays put.
        assert clamp_pan_offset(-100.0, 500.0, 300.0) == pytest.approx(-100.0)

    def test_positive_overshoot_clamps_to_zero(self):
        # A positive offset would show empty space on the left → clamp to 0.
        assert clamp_pan_offset(50.0, 500.0, 300.0) == pytest.approx(0.0)

    def test_negative_overshoot_clamps_to_min(self):
        # Past the right edge → clamp so the right edge meets the viewport.
        assert clamp_pan_offset(-999.0, 500.0, 300.0) == pytest.approx(-200.0)

    @pytest.mark.parametrize("offset,expected", [(0.0, 0.0), (-200.0, -200.0)])
    def test_exact_bounds_are_kept(self, offset, expected):
        assert clamp_pan_offset(offset, 500.0, 300.0) == pytest.approx(expected)


class TestZoomToRegion:
    CANVAS = (1000.0, 1000.0)
    LIMITS = (0.05, 50.0)

    def test_region_fills_canvas_and_centres(self):
        new_zoom, off_x, off_y = zoom_to_region(
            (200, 200, 400, 400), 1.0, (0.0, 0.0), self.CANVAS, self.LIMITS,
        )
        assert new_zoom == pytest.approx(5.0)  # 1000 / 200
        # The framed region's centre (300, 300) lands at the canvas centre.
        assert 300 * new_zoom + off_x == pytest.approx(500)
        assert 300 * new_zoom + off_y == pytest.approx(500)

    def test_corner_order_is_normalised(self):
        forward = zoom_to_region((200, 200, 400, 400), 1.0, (0.0, 0.0),
                                 self.CANVAS, self.LIMITS)
        reversed_ = zoom_to_region((400, 400, 200, 200), 1.0, (0.0, 0.0),
                                   self.CANVAS, self.LIMITS)
        assert forward == reversed_

    def test_tiny_region_clamped_to_zoom_max(self):
        new_zoom, _, _ = zoom_to_region(
            (500, 500, 510, 510), 1.0, (0.0, 0.0), self.CANVAS, self.LIMITS,
        )
        assert new_zoom == pytest.approx(50.0)  # 1000/10 capped at zoom_max

    def test_zero_area_region_does_not_divide_by_zero(self):
        new_zoom, off_x, off_y = zoom_to_region(
            (300, 300, 300, 300), 1.0, (0.0, 0.0), self.CANVAS, self.LIMITS,
        )
        assert new_zoom == pytest.approx(50.0)
        assert off_x == pytest.approx(1000 / 2 - 300 * 50.0)

    def test_accounts_for_current_zoom_and_offset(self):
        # zoom 2, panned (100, 100): screen rect 300..500 → image span 100 px.
        new_zoom, _, _ = zoom_to_region(
            (300, 300, 500, 500), 2.0, (100.0, 100.0), self.CANVAS, self.LIMITS,
        )
        assert new_zoom == pytest.approx(10.0)  # 1000 / 100
