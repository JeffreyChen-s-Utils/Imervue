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
from Imervue.gpu_image_view.deep_zoom_renderer import visible_tile_range


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
    # SAME helper. So the margins must come out symmetric even when width()
    # lags behind the authoritative resizeGL size.
    img_w = img_h = 500
    view = _FakeView(img_w, img_h, widget=(10, 10), last_resize=(1000, 1000))
    fit_view.fit_to_window(view)

    canvas_w, canvas_h = fit_view.canvas_size(view)
    left_margin = view.dz_offset_x
    right_margin = canvas_w - (view.dz_offset_x + img_w * view.zoom)
    top_margin = view.dz_offset_y
    bottom_margin = canvas_h - (view.dz_offset_y + img_h * view.zoom)

    assert left_margin == pytest.approx(right_margin)
    assert top_margin == pytest.approx(bottom_margin)
    assert left_margin > 0  # the lagging width() would have pushed it off-screen


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
