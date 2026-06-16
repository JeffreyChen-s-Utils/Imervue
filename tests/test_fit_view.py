"""Tests for fit_view — fit-to-window/width/height zoom + centring math.

Pure-Python: a fake view supplies the deep-zoom base dimensions, a canvas
size, and the deep-zoom overlay state (minimap is always on, filmstrip is
optional). No Qt / GL needed.

Reserve arithmetic used throughout (see ``minimap.minimap_geometry`` and
``filmstrip``): the minimap is capped at 180x140, sits ``MINIMAP_MARGIN`` (12)
in from the bottom, and the filmstrip band is ``ITEM_HEIGHT`` (72) +
2 * ``BAND_VPAD`` (8) = 88 px tall. For a square image the minimap is 140 tall,
so the reserved band is 140 + 12 = 152 px.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.gpu_image_view import fit_view

# Reserve for a square image (minimap height 140 + margin 12).
_SQUARE_RESERVE = 152
# Reserve for a 2:1 image (minimap height 90 + margin 12).
_WIDE_RESERVE = 102
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

def test_reserved_overlay_height_minimap_only():
    # Square image → minimap is 140 tall; reserve = 140 + 12 margin.
    view = _FakeView(500, 500, (1000, 1000))
    assert fit_view.reserved_overlay_height(view) == _SQUARE_RESERVE


def test_reserved_overlay_height_filmstrip_does_not_grow_tall_minimap():
    # Square image: the 152 px minimap reserve already clears the 88 px strip.
    view = _FakeView(500, 500, (1000, 1000), filmstrip=True, images=3)
    assert fit_view.reserved_overlay_height(view) == _SQUARE_RESERVE


def test_reserved_overlay_height_filmstrip_dominates_short_minimap():
    # Very wide image → minimap only ~72 px reserve, so the 88 px filmstrip
    # band is the taller overlay and sets the reserve.
    view = _FakeView(3000, 1000, (1000, 1000), filmstrip=True, images=3)
    assert fit_view.reserved_overlay_height(view) == _FILMSTRIP_BAND


def test_reserved_overlay_height_filmstrip_ignored_for_single_image():
    # Filmstrip is suppressed at one image, so a wide single image reserves
    # only its (short) minimap (height 60) + margin, not the 88 px band.
    view = _FakeView(3000, 1000, (1000, 1000), filmstrip=True, images=1)
    assert fit_view.reserved_overlay_height(view) == 60 + 12


def test_reserved_overlay_height_zero_in_grid_mode():
    view = _FakeView(500, 500, (1000, 1000), grid=True)
    assert fit_view.reserved_overlay_height(view) == 0


def test_reserved_overlay_height_zero_without_deep_zoom():
    view = _FakeView(0, 0, (1000, 1000), deep=False)
    assert fit_view.reserved_overlay_height(view) == 0


def test_content_size_subtracts_reserved_band_from_height_only():
    view = _FakeView(500, 500, (1000, 1000))
    assert fit_view.content_size(view) == (1000, 1000 - _SQUARE_RESERVE)


def test_content_size_floors_height_at_one_for_tiny_viewport():
    # A viewport shorter than the reserved band must not yield a non-positive
    # content height (which would drive fit_zoom negative and flip the image).
    view = _FakeView(500, 500, (120, 120))
    width, height = fit_view.content_size(view)
    assert width == 120
    assert height == 1
    assert fit_view.fit_zoom(view) > 0


# ---------------------------------------------------------------------------
# fit_zoom
# ---------------------------------------------------------------------------

def test_fit_zoom_caps_at_one():
    # Tiny image in a big canvas would zoom > 1 → capped to 1.0.
    view = _FakeView(100, 100, (1000, 1000))
    assert fit_view.fit_zoom(view) == 1.0


def test_fit_zoom_uses_min_dimension():
    # Wide image, square canvas → still width-limited even after the reserve.
    view = _FakeView(2000, 1000, (500, 500))
    assert fit_view.fit_zoom(view) == pytest.approx(0.25)


def test_fit_zoom_height_limited_by_reserved_band():
    # Square image in a square canvas: without the band fit would be 0.5, but
    # the 152 px reserve makes the content height (348) the binding dimension.
    view = _FakeView(1000, 1000, (10, 10), last_resize=(500, 500))
    assert fit_view.fit_zoom(view) == pytest.approx((500 - _SQUARE_RESERVE) / 1000)


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


# ---------------------------------------------------------------------------
# fit_to_window
# ---------------------------------------------------------------------------

def test_fit_to_window_letterboxes_above_overlays():
    view = _FakeView(500, 500, (1000, 1000))
    fit_view.fit_to_window(view)
    assert view.zoom == 1.0
    # Full-width centre is unchanged; vertical centre lifts into the 848 px
    # content area above the reserved band.
    assert view.dz_offset_x == 250
    assert view.dz_offset_y == (1000 - _SQUARE_RESERVE - 500) / 2
    assert view._user_locked_view is False


def test_fit_to_window_no_deep_zoom_is_noop():
    view = _FakeView(0, 0, (100, 100), deep=False)
    fit_view.fit_to_window(view)
    assert view.zoom == 99.0  # unchanged


def test_fit_to_window_centres_on_resize_size_not_lagging_width():
    # Regression: the "Home key shifts x/y" bug. width()/height() lag the
    # real layout, so centring must use the authoritative resizeGL size.
    view = _FakeView(500, 500, (10, 10), last_resize=(1000, 1000))
    fit_view.fit_to_window(view)
    assert view.zoom == 1.0
    assert view.dz_offset_x == 250  # (1000 - 500) / 2, NOT (10 - 500) / 2
    assert view.dz_offset_y == (1000 - _SQUARE_RESERVE - 500) / 2


# ---------------------------------------------------------------------------
# fit_to_width / fit_to_height
# ---------------------------------------------------------------------------

def test_fit_to_width_fills_width_and_centres_in_content():
    view = _FakeView(1000, 500, (500, 500))
    fit_view.fit_to_width(view)
    assert view.zoom == pytest.approx(0.5)
    assert view.dz_offset_x == 0
    # displayed height = 500 * 0.5 = 250; centred in (500 - 102) content height.
    assert view.dz_offset_y == pytest.approx((500 - _WIDE_RESERVE - 250) / 2)
    assert view.updated is True


def test_fit_to_height_fills_content_height():
    view = _FakeView(500, 1000, (500, 500))
    fit_view.fit_to_height(view)
    # Tall image → 152 px reserve; height fills the 348 px content area.
    assert view.zoom == pytest.approx((500 - _SQUARE_RESERVE) / 1000)
    assert view.dz_offset_y == 0
    assert view.dz_offset_x == pytest.approx(
        (500 - 500 * view.zoom) / 2)
    assert view.updated is True


def test_fit_to_width_no_deep_zoom_is_noop():
    view = _FakeView(0, 0, (100, 100), deep=False)
    fit_view.fit_to_width(view)
    assert view.updated is False


def test_fit_to_width_prefers_resize_size():
    view = _FakeView(1000, 500, (10, 10), last_resize=(500, 500))
    fit_view.fit_to_width(view)
    assert view.zoom == pytest.approx(0.5)  # against 500, not 10
    assert view.dz_offset_y == pytest.approx((500 - _WIDE_RESERVE - 250) / 2)


def test_fit_to_height_prefers_resize_size():
    view = _FakeView(500, 1000, (10, 10), last_resize=(500, 500))
    fit_view.fit_to_height(view)
    assert view.zoom == pytest.approx((500 - _SQUARE_RESERVE) / 1000)
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
