"""Tests for fit_view — fit-to-window/width/height zoom + centring math.

Pure-Python: a fake view supplies the deep-zoom base dimensions, a canvas
size, and the deep-zoom overlay state (the filmstrip is optional). No Qt / GL
needed.

Only the filmstrip reserves a bottom band: ``ITEM_HEIGHT`` (72) +
2 * ``BAND_VPAD`` (8) = 88 px. The minimap reserves nothing; it shows only
while the image overflows the canvas, over the image.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.gpu_image_view import fit_view

_FILMSTRIP_BAND = 88


class _FakeDeepZoom:
    def __init__(self, w, h):
        self.levels = [np.zeros((h, w, 4), dtype=np.uint8)]


class _FakeView:
    def __init__(self, img_w, img_h, canvas, *, last_resize=(0, 0), deep=True,
                 grid=False, filmstrip=False, images=1):
        self.deep_zoom = _FakeDeepZoom(img_w, img_h) if deep else None
        self._canvas = canvas
        self._last_resize_size = last_resize
        self.zoom = 99.0
        self.dz_offset_x = 0
        self.dz_offset_y = 0
        self._user_locked_view = True
        self.updated = False
        self.tile_grid_mode = grid
        self._filmstrip_enabled = filmstrip
        self.model = SimpleNamespace(images=list(range(images)))

    def width(self):
        return self._canvas[0]

    def height(self):
        return self._canvas[1]

    def update(self):
        self.updated = True


# ---------------------------------------------------------------------------
# reserved_overlay_height / content_size
# ---------------------------------------------------------------------------

def test_reserved_overlay_height_is_nothing_without_the_filmstrip():
    # The minimap reserves no band: a whole-image view gets the full height.
    view = _FakeView(500, 500, (1000, 1000))
    assert fit_view.reserved_overlay_height(view) == 0


def test_reserved_overlay_height_is_the_filmstrip_band():
    view = _FakeView(500, 500, (1000, 1000), filmstrip=True, images=3)
    assert fit_view.reserved_overlay_height(view) == _FILMSTRIP_BAND


def test_reserved_overlay_height_filmstrip_band_for_a_wide_image():
    view = _FakeView(3000, 1000, (1000, 1000), filmstrip=True, images=3)
    assert fit_view.reserved_overlay_height(view) == _FILMSTRIP_BAND


def test_reserved_overlay_height_filmstrip_ignored_for_single_image():
    # Filmstrip is suppressed at one image, so nothing is reserved.
    view = _FakeView(3000, 1000, (1000, 1000), filmstrip=True, images=1)
    assert fit_view.reserved_overlay_height(view) == 0


def test_reserved_overlay_height_zero_in_grid_mode():
    view = _FakeView(500, 500, (1000, 1000), grid=True)
    assert fit_view.reserved_overlay_height(view) == 0


def test_reserved_overlay_height_zero_without_deep_zoom():
    view = _FakeView(0, 0, (1000, 1000), deep=False)
    assert fit_view.reserved_overlay_height(view) == 0


def test_content_size_subtracts_reserved_band_from_height_only():
    view = _FakeView(500, 500, (1000, 1000), filmstrip=True, images=3)
    assert fit_view.content_size(view) == (1000, 1000 - _FILMSTRIP_BAND)


def test_content_size_is_the_whole_canvas_without_the_filmstrip():
    view = _FakeView(500, 500, (1000, 800))
    assert fit_view.content_size(view) == (1000, 800)


def test_content_size_floors_height_at_one_for_tiny_viewport():
    # A viewport shorter than the reserved band must not yield a non-positive
    # content height (which would drive fit_zoom negative and flip the image).
    view = _FakeView(500, 500, (60, 60), filmstrip=True, images=3)
    width, height = fit_view.content_size(view)
    assert width == 60
    assert height == 1
    assert fit_view.fit_zoom(view) > 0


# ---------------------------------------------------------------------------
# fit_zoom
# ---------------------------------------------------------------------------

def test_fit_zoom_enlarges_a_small_image_to_fill_the_canvas():
    view = _FakeView(100, 100, (1000, 1000))
    assert fit_view.fit_zoom(view) == pytest.approx(10.0)


def test_fit_zoom_stops_at_the_zoom_ceiling():
    from Imervue.gpu_image_view.input_controller_zoom import ZOOM_MAX
    view = _FakeView(1, 1, (1000, 1000))
    assert fit_view.fit_zoom(view) == pytest.approx(ZOOM_MAX)


def test_fit_zoom_just_below_the_ceiling_is_not_capped():
    view = _FakeView(25, 25, (1000, 1000))
    assert fit_view.fit_zoom(view) == pytest.approx(40.0)


def test_fit_zoom_uses_min_dimension():
    # Wide image, square canvas → still width-limited even after the reserve.
    view = _FakeView(2000, 1000, (500, 500))
    assert fit_view.fit_zoom(view) == pytest.approx(0.25)


def test_fit_zoom_height_limited_by_reserved_band():
    # Square image in a square canvas: without the band fit would be 0.5, but
    # the 88 px filmstrip makes the content height (412) the binding dimension.
    view = _FakeView(1000, 1000, (10, 10), last_resize=(500, 500),
                     filmstrip=True, images=3)
    assert fit_view.fit_zoom(view) == pytest.approx((500 - _FILMSTRIP_BAND) / 1000)


# ---------------------------------------------------------------------------
# minimap_visible (only while part of the image is off the canvas)
# ---------------------------------------------------------------------------

def test_minimap_hidden_while_the_whole_image_is_in_view():
    view = _FakeView(4000, 3000, (1600, 900))
    fit_view.fit_to_window(view)
    assert fit_view.minimap_visible(view) is False


def test_minimap_shown_once_zoomed_past_the_whole_image():
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.6
    assert fit_view.minimap_visible(view) is True


def test_minimap_hidden_just_inside_the_fit_slack():
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.3 * 1.0005   # rounding above the full-canvas fit of 0.3
    assert fit_view.minimap_visible(view) is False


def test_minimap_hidden_with_the_filmstrip_band_at_fit():
    view = _FakeView(4000, 3000, (1600, 900), filmstrip=True, images=3)
    fit_view.fit_to_window(view)
    assert fit_view.minimap_visible(view) is False


@pytest.mark.parametrize("kwargs", [{"deep": False}, {"grid": True}])
def test_minimap_hidden_outside_deep_zoom(kwargs):
    view = _FakeView(4000, 3000, (1600, 900), **kwargs)
    view.zoom = 5.0
    assert fit_view.minimap_visible(view) is False


# ---------------------------------------------------------------------------
# fits_within_canvas (re-fit a whole-image view rather than crop it)
# ---------------------------------------------------------------------------

def test_fits_within_canvas_true_at_full_canvas_fit():
    # 4000x3000 in 1600x900: full-canvas fit = 0.3; a remembered fit view is a
    # whole-image view → should be re-fit, not kept.
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.3
    assert fit_view.fits_within_canvas(view) is True


def test_fits_within_canvas_true_when_zoomed_out_below_fit():
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.2
    assert fit_view.fits_within_canvas(view) is True


def test_fits_within_canvas_false_when_zoomed_in():
    # Zoomed past the whole-image level → keep the user's view, don't re-fit.
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.6
    assert fit_view.fits_within_canvas(view) is False


def test_should_refit_on_load_always_fits_a_fresh_entry():
    # Not remembered → fit regardless of the leftover zoom (e.g. inherited from
    # a previous zoomed-in image), so opening from the tile wall always fits.
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 5.0  # leftover zoom-in from the previous image
    assert fit_view.should_refit_on_load(False, view) is True


def test_should_refit_on_load_refits_remembered_whole_image():
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.3  # remembered at the whole-image fit
    assert fit_view.should_refit_on_load(True, view) is True


def test_should_refit_on_load_keeps_remembered_zoom_in():
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.6  # genuine remembered zoom-in
    assert fit_view.should_refit_on_load(True, view) is False


def test_should_refit_on_load_refits_when_dimensions_changed():
    # A rotate swaps width/height; the remembered zoom was saved against the
    # pre-rotation dims, so even a genuine zoom-in value must refit to the new
    # shape instead of overflowing the canvas.
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.6  # would be kept if dims matched (keeps_remembered_zoom_in)
    assert fit_view.should_refit_on_load(
        True, view, remembered_dims=(3000, 4000)) is True


def test_should_refit_on_load_keeps_zoom_when_dimensions_match():
    # Same dims (a tonal recipe edit, not a geometry change) → preserve the
    # user's genuine zoom-in instead of snapping back to fit.
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.6
    assert fit_view.should_refit_on_load(
        True, view, remembered_dims=(4000, 3000)) is False


def test_should_refit_on_load_refits_remembered_fit_on_smaller_canvas():
    # A whole-image fit saved on a LARGER screen reloaded on a SMALLER canvas:
    # its zoom (0.5) exceeds this canvas's fit (~0.225), so fits_within_canvas
    # alone would mistake it for a zoom-in and keep it, opening cropped/too big.
    # was_locked=False marks it a fit, so it re-fits.
    view = _FakeView(4000, 3000, (1200, 675))
    view.zoom = 0.5
    assert fit_view.should_refit_on_load(
        True, view, remembered_dims=(4000, 3000), was_locked=False) is True


def test_should_refit_on_load_keeps_locked_zoom_in_that_no_longer_fits():
    # A deliberate user zoom-in (was_locked=True) is preserved even though it
    # exceeds the current canvas's fit.
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.6
    assert fit_view.should_refit_on_load(
        True, view, remembered_dims=(4000, 3000), was_locked=True) is False


def test_should_refit_on_load_none_dims_falls_back_to_fit_test():
    # Legacy memory entries saved without dims → behave exactly as before.
    view = _FakeView(4000, 3000, (1600, 900))
    view.zoom = 0.6
    assert fit_view.should_refit_on_load(True, view, remembered_dims=None) is False


# ---------------------------------------------------------------------------
# fit_to_window
# ---------------------------------------------------------------------------

def test_fit_to_window_fills_the_canvas():
    view = _FakeView(500, 500, (1000, 1000))
    fit_view.fit_to_window(view)
    assert view.zoom == pytest.approx(2.0)
    assert view.dz_offset_x == pytest.approx(0)
    assert view.dz_offset_y == pytest.approx(0)
    assert view._user_locked_view is False


def test_fit_to_window_letterboxes_above_the_filmstrip():
    view = _FakeView(500, 500, (1000, 1000), filmstrip=True, images=3)
    fit_view.fit_to_window(view)
    content_h = 1000 - _FILMSTRIP_BAND
    assert view.zoom == pytest.approx(content_h / 500)
    # Full-width centre; the image fills the content area above the band.
    assert view.dz_offset_x == pytest.approx((1000 - content_h) / 2)
    assert view.dz_offset_y == pytest.approx(0)


def test_fit_to_window_no_deep_zoom_is_noop():
    view = _FakeView(0, 0, (100, 100), deep=False)
    fit_view.fit_to_window(view)
    assert view.zoom == 99.0  # unchanged


def test_fit_to_window_centres_on_resize_size_not_lagging_width():
    # Regression: the "Home key shifts x/y" bug. width()/height() lag the
    # real layout, so centring must use the authoritative resizeGL size.
    view = _FakeView(250, 500, (10, 10), last_resize=(1000, 1000))
    fit_view.fit_to_window(view)
    assert view.zoom == pytest.approx(2.0)
    assert view.dz_offset_x == pytest.approx(250)  # (1000 - 500) / 2, NOT from 10
    assert view.dz_offset_y == pytest.approx(0)


# ---------------------------------------------------------------------------
# fit_to_width / fit_to_height
# ---------------------------------------------------------------------------

def test_fit_to_width_fills_width_and_centres_in_content():
    view = _FakeView(1000, 500, (500, 500))
    fit_view.fit_to_width(view)
    assert view.zoom == pytest.approx(0.5)
    assert view.dz_offset_x == 0
    # displayed height = 500 * 0.5 = 250; centred in the 500 px content height.
    assert view.dz_offset_y == pytest.approx((500 - 250) / 2)
    assert view.updated is True


def test_fit_to_height_fills_content_height():
    view = _FakeView(500, 1000, (500, 500))
    fit_view.fit_to_height(view)
    # Tall image, no filmstrip: height fills the whole 500 px canvas.
    assert view.zoom == pytest.approx(0.5)
    assert view.dz_offset_y == 0
    assert view.dz_offset_x == pytest.approx(
        (500 - 500 * view.zoom) / 2)
    assert view.updated is True


def test_fit_to_width_locks_the_view():
    # An explicit fit-width is the user taking control → lock so a later resize
    # settle re-fit can't revert it to fit-to-window.
    view = _FakeView(1000, 500, (500, 500))
    view._user_locked_view = False
    fit_view.fit_to_width(view)
    assert view._user_locked_view is True


def test_fit_to_height_locks_the_view():
    view = _FakeView(500, 1000, (500, 500))
    view._user_locked_view = False
    fit_view.fit_to_height(view)
    assert view._user_locked_view is True


def test_fit_to_width_no_deep_zoom_is_noop():
    view = _FakeView(0, 0, (100, 100), deep=False)
    fit_view.fit_to_width(view)
    assert view.updated is False


def test_fit_to_width_prefers_resize_size():
    view = _FakeView(1000, 500, (10, 10), last_resize=(500, 500))
    fit_view.fit_to_width(view)
    assert view.zoom == pytest.approx(0.5)  # against 500, not 10
    assert view.dz_offset_y == pytest.approx((500 - 250) / 2)


def test_fit_to_height_prefers_resize_size():
    view = _FakeView(500, 1000, (10, 10), last_resize=(500, 500))
    fit_view.fit_to_height(view)
    assert view.zoom == pytest.approx(0.5)
    assert view.dz_offset_x == pytest.approx((500 - 500 * view.zoom) / 2)


# ---------------------------------------------------------------------------
# canvas_size (unchanged behaviour)
# ---------------------------------------------------------------------------

def test_canvas_size_prefers_last_resize():
    view = _FakeView(100, 100, (10, 10), last_resize=(800, 600))
    assert fit_view.canvas_size(view) == (800, 600)


def test_canvas_size_falls_back_to_widget_size():
    view = _FakeView(100, 100, (640, 480))
    assert fit_view.canvas_size(view) == (640, 480)


def test_canvas_size_clamps_zero_widget_size():
    # No resizeGL yet AND a degenerate 0x0 widget → never returns 0
    # (the fit math divides by it).
    view = _FakeView(100, 100, (0, 0))
    assert fit_view.canvas_size(view) == (1, 1)


# ---------------------------------------------------------------------------
# invalidate_canvas_size (hide/reshow stale-cache fix)
# ---------------------------------------------------------------------------

def test_invalidate_canvas_size_clears_the_cache():
    view = _FakeView(100, 100, (640, 480), last_resize=(800, 600))
    fit_view.invalidate_canvas_size(view)
    assert view._last_resize_size == (0, 0)


def test_canvas_size_uses_live_geometry_after_invalidation():
    # After a hide invalidates the stale cache, the next fit reads the live
    # (now-correct) widget size instead of the pre-hide resizeGL size.
    view = _FakeView(100, 100, (640, 480), last_resize=(800, 600))
    fit_view.invalidate_canvas_size(view)
    assert fit_view.canvas_size(view) == (640, 480)


# ---------------------------------------------------------------------------
# should_settle_refit (deferred deep-zoom entry re-fit)
# ---------------------------------------------------------------------------

def test_should_settle_refit_true_for_unlocked_deep_zoom():
    view = _FakeView(100, 100, (800, 600))
    view._user_locked_view = False
    assert fit_view.should_settle_refit(view) is True


def test_should_settle_refit_false_when_user_locked():
    # A deliberate zoom-in must never be snapped back by the settle fit.
    view = _FakeView(100, 100, (800, 600))
    view._user_locked_view = True
    assert fit_view.should_settle_refit(view) is False


def test_should_settle_refit_false_without_deep_zoom():
    view = _FakeView(100, 100, (800, 600), deep=False)
    view._user_locked_view = False
    assert fit_view.should_settle_refit(view) is False


# ---------------------------------------------------------------------------
# refit_action (what a canvas-size change does to the current view)
# ---------------------------------------------------------------------------

def test_refit_action_fits_an_unlocked_view():
    view = _FakeView(100, 100, (800, 600))
    view._user_locked_view = False
    assert fit_view.refit_action(view) == fit_view.REFIT_FIT


def test_refit_action_clamps_a_locked_view():
    # A deliberate zoom-in keeps its zoom; only its pan is re-clamped so the
    # new (maybe smaller) viewport can't strand it off-screen.
    view = _FakeView(100, 100, (800, 600))
    view._user_locked_view = True
    assert fit_view.refit_action(view) == fit_view.REFIT_CLAMP


def test_refit_action_none_without_deep_zoom():
    view = _FakeView(100, 100, (800, 600), deep=False)
    view._user_locked_view = False
    assert fit_view.refit_action(view) == fit_view.REFIT_NONE


def test_refit_action_none_in_tile_grid_mode():
    view = _FakeView(100, 100, (800, 600), grid=True)
    view._user_locked_view = False
    assert fit_view.refit_action(view) == fit_view.REFIT_NONE


def test_refit_action_tolerates_a_view_without_the_lock_flag():
    # Defensive: partial fakes / a view built before the flag exists must not
    # raise — an unknown lock state reads as "whole-image", i.e. re-fit.
    view = _FakeView(100, 100, (800, 600))
    del view._user_locked_view
    assert fit_view.refit_action(view) == fit_view.REFIT_FIT
