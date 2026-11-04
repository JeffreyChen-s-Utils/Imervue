"""Tests for deep_zoom_renderer's pure geometry helpers.

The renderer itself drives the live GL context (``# pragma: no cover``), but
the tile-visibility math and its agreement with the fit-to-window centring are
pure and unit-testable. These tests pin the "Home key shifts x/y" regression:
the renderer and the fit math MUST read the same canvas size.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.gpu_image_view import fit_view
from Imervue.gpu_image_view.deep_zoom_renderer import (
    DeepZoomRenderer,
    letterbox_band_rect,
    visible_tile_range,
)


def test_letterbox_band_rect_covers_reserved_bottom_strip():
    # Screen-space (top-origin): the 152 px band spans the full width across the
    # bottom, starting at y = canvas_h - reserved.
    assert letterbox_band_rect(1000, 800, 152) == (0.0, 648.0, 1000, 800)


def test_letterbox_band_rect_floors_top_when_band_exceeds_canvas():
    # A viewport shorter than the band fills the whole height (top floored at 0).
    assert letterbox_band_rect(1000, 100, 152) == (0.0, 0.0, 1000, 100)


def test_visible_tile_range_origin():
    # Whole 1000x1000 canvas at 1:1, no pan → tiles (0,0)..(3,3) for 256px.
    assert visible_tile_range(1000, 1000, 1.0, 1.0, 0, 0, 256) == (0, 3, 0, 3)


def test_visible_tile_range_panned():
    # Pan right by 512 px (negative offset) → viewport starts at image x=512.
    tx0, tx1, ty0, ty1 = visible_tile_range(1000, 1000, 1.0, 1.0, -512, 0, 256)
    assert (tx0, tx1) == (2, 5)
    assert (ty0, ty1) == (0, 3)


def test_visible_tile_range_scaled():
    # At 0.5 scale the viewport covers twice as many image pixels.
    tx0, tx1, _, _ = visible_tile_range(1000, 1000, 0.5, 0.5, 0, 0, 256)
    assert (tx0, tx1) == (0, 2000 // 256)  # right edge = 2000 image px → tile 7


def test_renderer_and_fit_agree_on_centre():
    # Regression for the off-centre Home-key bug: fit_to_window centres the
    # image using fit_view.canvas_size; the renderer maps it to screen with the
    # SAME helper, so width() lagging the authoritative resizeGL size can't push
    # the image off-screen. Horizontally the margins stay symmetric; vertically
    # the image is letterboxed above the reserved overlay band, so the extra
    # space all sits at the bottom (bottom margin = top margin + the reserve).
    # A 2:1 image fills the width, leaving room above and below.
    img_w, img_h = 500, 250
    view = _FakeView(img_w, img_h, widget=(10, 10), last_resize=(1000, 1000))
    fit_view.fit_to_window(view)

    canvas_w, canvas_h = fit_view.canvas_size(view)
    reserve = fit_view.reserved_overlay_height(view)
    left_margin = view.dz_offset_x
    right_margin = canvas_w - (view.dz_offset_x + img_w * view.zoom)
    top_margin = view.dz_offset_y
    bottom_margin = canvas_h - (view.dz_offset_y + img_h * view.zoom)

    assert left_margin == pytest.approx(right_margin)
    assert bottom_margin - top_margin == pytest.approx(reserve)
    assert top_margin > 0
    assert left_margin == pytest.approx(0)  # fills the width of 1000, not of 10


class _FakeDeepZoom:
    def __init__(self, w, h):
        self.levels = [np.zeros((h, w, 4), dtype=np.uint8)]


class _FakeView:
    def __init__(self, img_w, img_h, *, widget, last_resize):
        self.deep_zoom = _FakeDeepZoom(img_w, img_h)
        self._widget = widget
        self._last_resize_size = last_resize
        self.zoom = 1.0
        self.dz_offset_x = 0
        self.dz_offset_y = 0
        self._user_locked_view = True

    def width(self):
        return self._widget[0]

    def height(self):
        return self._widget[1]

    def update(self):
        pass


def test_minimap_rect_is_none_while_the_whole_image_is_in_view():
    view = _FakeView(500, 250, widget=(1000, 1000), last_resize=(1000, 1000))
    fit_view.fit_to_window(view)
    assert DeepZoomRenderer(view).current_minimap_rect() is None


def test_minimap_rect_appears_once_zoomed_in():
    view = _FakeView(500, 250, widget=(1000, 1000), last_resize=(1000, 1000))
    view.zoom = 4.0
    x, y, w, h = DeepZoomRenderer(view).current_minimap_rect()
    assert (w, h) == (180, 90)
    assert (x + w, y + h) == (1000 - 12, 1000 - 12)   # bottom-right corner, over the image


def test_paint_minimap_draws_the_filmstrip_band_without_the_minimap(monkeypatch):
    from Imervue.gpu_image_view import deep_zoom_renderer as mod
    monkeypatch.setattr(mod, "glEnable", lambda *_a: None)
    monkeypatch.setattr(mod, "glBlendFunc", lambda *_a: None)
    view = _FakeView(500, 250, widget=(1000, 1000), last_resize=(1000, 1000))
    fit_view.fit_to_window(view)
    renderer = DeepZoomRenderer(view)
    view.renderer = type("R", (), {"use_shaders": True})()
    calls = []
    monkeypatch.setattr(renderer, "_draw_letterbox_band", lambda: calls.append("band"))
    monkeypatch.setattr(renderer, "_draw_minimap_background", lambda _r: calls.append("mm"))
    renderer.paint_minimap()
    assert calls == ["band"]


def test_paint_minimap_without_an_image_draws_nothing(monkeypatch):
    view = _FakeView(500, 250, widget=(1000, 1000), last_resize=(1000, 1000))
    view.deep_zoom = None
    renderer = DeepZoomRenderer(view)
    calls = []
    monkeypatch.setattr(renderer, "_draw_letterbox_band", lambda: calls.append("band"))
    renderer.paint_minimap()
    assert calls == []
