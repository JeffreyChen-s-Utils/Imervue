"""Tests for the pure deep-zoom view-navigation helpers."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.view_nav import toggle_zoom_target, zoom_about_point


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
