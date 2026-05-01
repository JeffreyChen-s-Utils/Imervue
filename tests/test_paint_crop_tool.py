"""Tests for the crop tool — aspect snap helper + dispatcher commit."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.crop_tool import (
    ASPECT_PRESETS,
    DEFAULT_ASPECT,
    normalise_rect,
    snap_to_aspect,
)
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.tool_dispatcher import ToolDispatcher, _CropTool
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# snap_to_aspect
# ---------------------------------------------------------------------------


def test_snap_freeform_returns_unchanged():
    out = snap_to_aspect(0, 0, 10, 4, None)
    assert out == (0.0, 0.0, 10.0, 4.0)


def test_snap_square_uses_wider_axis():
    """Drag of 10×4 with 1:1 → 10×10 (width was the dominant axis)."""
    _x0, _y0, x1, y1 = snap_to_aspect(0, 0, 10, 4, (1, 1))
    assert x1 == 10
    assert y1 == 10


def test_snap_square_uses_taller_axis():
    """Drag of 4×10 with 1:1 → 10×10 (height was dominant)."""
    _x0, _y0, x1, y1 = snap_to_aspect(0, 0, 4, 10, (1, 1))
    assert x1 == 10
    assert y1 == 10


def test_snap_widescreen_16_9_extends_height():
    """A 32×10 drag with 16:9 should keep width at 32 (= 32/16 * 9 = 18)."""
    _x0, _y0, x1, y1 = snap_to_aspect(0, 0, 32, 10, (16, 9))
    assert x1 == 32
    assert pytest.approx(y1, abs=0.01) == 18.0


def test_snap_preserves_drag_direction():
    """Negative drag (top-left to bottom-right reversed) keeps its
    sign so the anchor corner stays put."""
    _x0, _y0, x1, y1 = snap_to_aspect(20, 20, -10, 0, (1, 1))
    # dx is -30 (from 20 to -10), dy is -20 (from 20 to 0). |dx|>|dy|
    # so width dominates; new dy should match -|dx| = -30.
    assert y1 < 20    # moved up


def test_snap_zero_drag_returns_input():
    out = snap_to_aspect(5, 5, 5, 5, (4, 3))
    assert out == (5.0, 5.0, 5.0, 5.0)


def test_snap_rejects_zero_aspect_component():
    with pytest.raises(ValueError):
        snap_to_aspect(0, 0, 4, 4, (0, 1))


# ---------------------------------------------------------------------------
# normalise_rect
# ---------------------------------------------------------------------------


def test_normalise_returns_positive_rect():
    out = normalise_rect(20, 20, 4, 4, (32, 32))
    assert out == (4, 4, 16, 16)


def test_normalise_clipped_to_canvas():
    out = normalise_rect(0, 0, 100, 100, (32, 32))
    assert out == (0, 0, 32, 32)


def test_normalise_zero_area_returns_none():
    assert normalise_rect(0, 0, 0, 0, (32, 32)) is None


def test_normalise_off_canvas_returns_none():
    """A drag entirely off the canvas yields no in-bounds rect."""
    assert normalise_rect(40, 40, 100, 100, (32, 32)) is None


# ---------------------------------------------------------------------------
# ASPECT_PRESETS catalogue
# ---------------------------------------------------------------------------


def test_aspect_presets_has_freeform_first():
    assert ASPECT_PRESETS[0] == ("Freeform", None)


def test_aspect_presets_match_documented_set():
    names = {name for name, _aspect in ASPECT_PRESETS}
    assert names >= {"Freeform", "1:1", "16:9", "9:16", "3:2"}


def test_default_aspect_is_freeform():
    assert DEFAULT_ASPECT is None


# ---------------------------------------------------------------------------
# Dispatcher tool — crop commits via workspace
# ---------------------------------------------------------------------------


def _press(x, y):
    return PointerEvent(
        phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0,
    )


def _release(x, y):
    return PointerEvent(
        phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0,
    )


def test_dispatcher_registers_crop_tool(qapp):
    state = ts.load_tool_state()
    canvas = np.zeros((32, 32, 4), dtype=np.uint8)
    disp = ToolDispatcher(state, image_provider=lambda: canvas)
    assert "crop" in disp._handlers   # noqa: SLF001
    assert isinstance(disp._handlers["crop"], _CropTool)   # noqa: SLF001


def test_crop_without_workspace_is_noop(qapp):
    state = ts.load_tool_state()
    canvas = np.zeros((32, 32, 4), dtype=np.uint8)
    tool = _CropTool(state)
    tool.handle(_press(4, 4), canvas)
    handled = tool.handle(_release(20, 20), canvas)
    assert handled is False


def test_crop_commits_via_workspace(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        h_before, w_before = document.shape
        crop_tool = ws._dispatcher._handlers["crop"]   # noqa: SLF001
        # Drag a 50×50 rect from (10, 10) to (60, 60).
        crop_tool.handle(_press(10, 10), ws.canvas().current_image())
        handled = crop_tool.handle(_release(60, 60), ws.canvas().current_image())
        assert handled is True
        h_after, w_after = document.shape
        assert h_after == 50
        assert w_after == 50
        assert (h_after, w_after) != (h_before, w_before)
    finally:
        ws.deleteLater()


def test_crop_with_aspect_preset_snaps_to_ratio(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        ws.state().crop_aspect = (1, 1)
        crop_tool = ws._dispatcher._handlers["crop"]   # noqa: SLF001
        crop_tool.handle(_press(10, 10), ws.canvas().current_image())
        # Drag 60 wide, 30 tall — aspect 1:1 should square to 60×60.
        handled = crop_tool.handle(_release(70, 40), ws.canvas().current_image())
        assert handled is True
        h_after, w_after = document.shape
        assert h_after == w_after
    finally:
        ws.deleteLater()


def test_crop_zero_drag_is_noop(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        before = document.shape
        crop_tool = ws._dispatcher._handlers["crop"]   # noqa: SLF001
        crop_tool.handle(_press(20, 20), ws.canvas().current_image())
        handled = crop_tool.handle(_release(20, 20), ws.canvas().current_image())
        assert handled is False
        assert document.shape == before
    finally:
        ws.deleteLater()


def test_crop_release_without_press_is_noop(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        before = document.shape
        crop_tool = ws._dispatcher._handlers["crop"]   # noqa: SLF001
        crop_tool.handle(_release(50, 50), ws.canvas().current_image())
        assert document.shape == before
    finally:
        ws.deleteLater()
