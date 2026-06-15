"""Tests for fit_view — fit-to-window/width/height zoom + centring math.

Pure-Python: a fake view supplies the deep-zoom base dimensions and a
canvas size; no Qt / GL needed.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.gpu_image_view import fit_view


class _FakeDeepZoom:
    def __init__(self, w, h):
        self.levels = [np.zeros((h, w, 4), dtype=np.uint8)]


class _FakeView:
    def __init__(self, img_w, img_h, canvas, *, last_resize=(0, 0), deep=True):
        self.deep_zoom = _FakeDeepZoom(img_w, img_h) if deep else None
        self._canvas = canvas
        self._last_resize_size = last_resize
        self.zoom = 99.0
        self.dz_offset_x = 0
        self.dz_offset_y = 0
        self._user_locked_view = True
        self.updated = False

    def width(self):
        return self._canvas[0]

    def height(self):
        return self._canvas[1]

    def update(self):
        self.updated = True


def test_fit_zoom_caps_at_one():
    # Tiny image in a big canvas would zoom > 1 → capped to 1.0.
    view = _FakeView(100, 100, (1000, 1000))
    assert fit_view.fit_zoom(view) == 1.0


def test_fit_zoom_uses_min_dimension():
    # Wide image, square canvas → height-limited.
    view = _FakeView(2000, 1000, (500, 500))
    assert fit_view.fit_zoom(view) == pytest.approx(0.25)


def test_fit_zoom_prefers_last_resize_size():
    view = _FakeView(1000, 1000, (10, 10), last_resize=(500, 500))
    # Uses 500 (resize) not 10 (width) → 0.5.
    assert fit_view.fit_zoom(view) == pytest.approx(0.5)


def test_fit_to_window_centres_and_unlocks():
    view = _FakeView(500, 500, (1000, 1000))
    fit_view.fit_to_window(view)
    assert view.zoom == 1.0
    # Centred: (1000 - 500) / 2 = 250.
    assert view.dz_offset_x == 250
    assert view.dz_offset_y == 250
    assert view._user_locked_view is False


def test_fit_to_window_no_deep_zoom_is_noop():
    view = _FakeView(0, 0, (100, 100), deep=False)
    fit_view.fit_to_window(view)
    assert view.zoom == 99.0  # unchanged


def test_fit_to_width_fills_width():
    view = _FakeView(1000, 500, (500, 500))
    fit_view.fit_to_width(view)
    assert view.zoom == pytest.approx(0.5)
    assert view.dz_offset_x == 0
    # displayed height = 500 * 0.5 = 250; centred vertically → 125.
    assert view.dz_offset_y == pytest.approx(125)
    assert view.updated is True


def test_fit_to_height_fills_height():
    view = _FakeView(500, 1000, (500, 500))
    fit_view.fit_to_height(view)
    assert view.zoom == pytest.approx(0.5)
    assert view.dz_offset_y == 0
    assert view.dz_offset_x == pytest.approx(125)
    assert view.updated is True


def test_fit_to_width_no_deep_zoom_is_noop():
    view = _FakeView(0, 0, (100, 100), deep=False)
    fit_view.fit_to_width(view)
    assert view.updated is False


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


def test_fit_to_window_centres_on_resize_size_not_lagging_width():
    # Regression: the "Home key shifts x/y" bug. width()/height() lag the
    # real layout, so centring must use the authoritative resizeGL size or
    # the offsets disagree with where the renderer maps the image.
    view = _FakeView(500, 500, (10, 10), last_resize=(1000, 1000))
    fit_view.fit_to_window(view)
    assert view.zoom == 1.0
    assert view.dz_offset_x == 250  # (1000 - 500) / 2, NOT (10 - 500) / 2
    assert view.dz_offset_y == 250


def test_fit_to_width_prefers_resize_size():
    view = _FakeView(1000, 500, (10, 10), last_resize=(500, 500))
    fit_view.fit_to_width(view)
    assert view.zoom == pytest.approx(0.5)
    assert view.dz_offset_y == pytest.approx(125)  # centred against 500, not 10


def test_fit_to_height_prefers_resize_size():
    view = _FakeView(500, 1000, (10, 10), last_resize=(500, 500))
    fit_view.fit_to_height(view)
    assert view.zoom == pytest.approx(0.5)
    assert view.dz_offset_x == pytest.approx(125)  # centred against 500, not 10
