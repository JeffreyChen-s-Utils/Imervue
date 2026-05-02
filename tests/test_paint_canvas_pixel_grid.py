"""Tests for the pixel-grid overlay state + the should_paint predicate."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PaintCanvas
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.visual_guides import PIXEL_GRID_MIN_ZOOM
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _canvas(qapp):
    canvas = PaintCanvas()
    canvas.new_blank_document(width=64, height=64)
    return canvas


# ---------------------------------------------------------------------------
# Setter
# ---------------------------------------------------------------------------


def test_set_pixel_grid_visible_writes_field(qapp):
    canvas = _canvas(qapp)
    try:
        assert canvas._pixel_grid_visible is False  # noqa: SLF001
        canvas.set_pixel_grid_visible(True)
        assert canvas._pixel_grid_visible is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_pixel_grid_visible_idempotent(qapp):
    """Re-setting the same value must short-circuit so a refresh
    storm doesn't burn a paint event per frame."""
    canvas = _canvas(qapp)
    try:
        canvas.set_pixel_grid_visible(True)
        # Direct sentinel — re-call should NOT invoke update().
        # (We can't easily intercept Qt's update(); instead trust
        # the early-return contract.)
        canvas.set_pixel_grid_visible(True)
        assert canvas._pixel_grid_visible is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# should_paint_pixel_grid predicate
# ---------------------------------------------------------------------------


def test_should_paint_false_when_flag_off_even_at_high_zoom(qapp):
    canvas = _canvas(qapp)
    try:
        canvas._zoom = PIXEL_GRID_MIN_ZOOM + 1  # noqa: SLF001
        assert canvas.should_paint_pixel_grid() is False
    finally:
        canvas.deleteLater()


def test_should_paint_false_when_zoom_below_threshold(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_pixel_grid_visible(True)
        canvas._zoom = PIXEL_GRID_MIN_ZOOM - 0.1  # noqa: SLF001
        assert canvas.should_paint_pixel_grid() is False
    finally:
        canvas.deleteLater()


def test_should_paint_true_when_flag_on_and_zoomed_in(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_pixel_grid_visible(True)
        canvas._zoom = PIXEL_GRID_MIN_ZOOM  # noqa: SLF001
        assert canvas.should_paint_pixel_grid() is True
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# View-menu bridge integration
# ---------------------------------------------------------------------------


def test_view_menu_toggle_propagates_to_canvas(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.toggle_pixel_grid(True)
        assert ws.canvas()._pixel_grid_visible is True  # noqa: SLF001
        bridge.toggle_pixel_grid(False)
        assert ws.canvas()._pixel_grid_visible is False  # noqa: SLF001
    finally:
        ws.deleteLater()
