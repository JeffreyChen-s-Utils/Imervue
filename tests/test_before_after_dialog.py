"""Tests for the Before/After split-slider comparison.

The split geometry is pure and tested without Qt; the widget / dialog get a
qapp smoke test (plain QWidget — no QOpenGLWidget, so no headless-CI skip).
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.gui.before_after_dialog import (
    BeforeAfterDialog,
    BeforeAfterView,
    clamp_fraction,
    divider_x,
    fit_rect,
    fraction_from_x,
    near_divider,
    open_before_after_dialog,
    rgba_to_qimage,
)


def _rgba(value, h=8, w=12):
    arr = np.full((h, w, 4), value, dtype=np.uint8)
    arr[..., 3] = 255
    return arr


class TestSplitGeometry:
    @pytest.mark.parametrize("raw,expected", [
        (-0.5, 0.0), (0.0, 0.0), (0.4, 0.4), (1.0, 1.0), (2.0, 1.0),
    ])
    def test_clamp_fraction(self, raw, expected):
        assert clamp_fraction(raw) == expected

    def test_divider_x_spans_the_width(self):
        assert divider_x(0.0, 200) == 0
        assert divider_x(0.5, 200) == 100
        assert divider_x(1.0, 200) == 200

    def test_fraction_from_x_clamps_and_guards_zero_width(self):
        assert fraction_from_x(50, 200) == pytest.approx(0.25)
        assert fraction_from_x(-10, 200) == pytest.approx(0.0)
        assert fraction_from_x(999, 200) == pytest.approx(1.0)
        assert fraction_from_x(5, 0) == pytest.approx(0.0)  # empty strip → no divide-by-zero

    def test_near_divider_grab_zone(self):
        assert near_divider(100, 0.5, 200) is True
        assert near_divider(108, 0.5, 200, tolerance=10) is True
        assert near_divider(140, 0.5, 200, tolerance=10) is False

    def test_fit_rect_landscape_is_width_limited_and_centred(self):
        # 200x100 into 400x400 → fills the 400 width, letterboxed vertically.
        assert fit_rect(200, 100, 400, 400) == (0, 100, 400, 200)

    def test_fit_rect_portrait_is_height_limited_and_centred(self):
        assert fit_rect(100, 200, 400, 400) == (100, 0, 200, 400)

    def test_fit_rect_zero_dims_collapse_to_origin(self):
        assert fit_rect(0, 100, 400, 400) == (0, 0, 0, 0)
        assert fit_rect(100, 100, 0, 400) == (0, 0, 0, 0)


class TestRgbaToQimage:
    def test_round_trip_size(self, qapp):
        img = rgba_to_qimage(_rgba(120, h=8, w=12))
        assert (img.width(), img.height()) == (12, 8)
        assert not img.isNull()

    def test_invalid_array_raises(self, qapp):
        with pytest.raises(ValueError, match="HxWx4 uint8"):
            rgba_to_qimage(np.zeros((4, 4, 3), dtype=np.uint8))


class TestBeforeAfterView:
    def _view(self):
        view = BeforeAfterView(rgba_to_qimage(_rgba(0)), rgba_to_qimage(_rgba(255)))
        view.resize(400, 300)
        return view

    def test_default_divider_is_centre(self, qapp):
        assert self._view().fraction() == pytest.approx(0.5)

    def test_set_divider_from_widget_x_updates_fraction(self, qapp):
        view = self._view()
        rx, _, rw, _ = view._display_rect()
        view.set_divider_from_widget_x(rx + rw * 0.25)
        assert view.fraction() == pytest.approx(0.25, abs=0.02)

    def test_divider_clamps_outside_image_rect(self, qapp):
        view = self._view()
        rx, _, rw, _ = view._display_rect()
        view.set_divider_from_widget_x(rx - 100)
        assert view.fraction() == pytest.approx(0.0)
        view.set_divider_from_widget_x(rx + rw + 100)
        assert view.fraction() == pytest.approx(1.0)


class TestBeforeAfterDialog:
    def test_builds_with_images(self, qapp):
        dlg = BeforeAfterDialog(
            rgba_to_qimage(_rgba(0)), rgba_to_qimage(_rgba(255)), "title")
        assert dlg.windowTitle() == "title"
        assert isinstance(dlg._view, BeforeAfterView)


def test_open_guard_no_images_is_noop():
    # No current image → returns without constructing a dialog or raising.
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_before_after_dialog(viewer)
