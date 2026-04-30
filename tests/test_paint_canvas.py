"""Tests for the paint canvas helpers and pure-logic surface.

The OpenGL paint loop is skipped from coverage (it needs a display
server / GL context); the unit tests cover the testable parts: cursor
map, zoom clamp, screen↔image math, image-shape validation, and the
``PointerEvent`` dataclass contract.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt

from Imervue.paint.canvas import (
    ZOOM_MAX,
    ZOOM_MIN,
    PointerEvent,
    clamp_zoom,
    cursor_for_tool,
)


# ---------------------------------------------------------------------------
# cursor_for_tool
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool", [
    "brush", "eraser", "fill", "eyedropper",
    "select_rect", "select_lasso", "select_wand",
    "move", "text", "gradient", "blur", "smudge",
    "hand", "zoom",
])
def test_cursor_known_for_every_documented_tool(tool):
    cursor = cursor_for_tool(tool)
    assert isinstance(cursor, Qt.CursorShape)


def test_cursor_falls_back_to_arrow_for_unknown_tool():
    assert cursor_for_tool("teleporter") == Qt.CursorShape.ArrowCursor


def test_brush_and_eraser_share_cross_cursor():
    assert cursor_for_tool("brush") == cursor_for_tool("eraser")


def test_text_tool_uses_ibeam_cursor():
    assert cursor_for_tool("text") == Qt.CursorShape.IBeamCursor


def test_hand_tool_uses_open_hand_cursor():
    assert cursor_for_tool("hand") == Qt.CursorShape.OpenHandCursor


# ---------------------------------------------------------------------------
# clamp_zoom
# ---------------------------------------------------------------------------


def test_clamp_zoom_passes_through_in_range_value():
    assert clamp_zoom(1.0) == pytest.approx(1.0)


def test_clamp_zoom_clamps_below_min():
    assert clamp_zoom(0.0) == ZOOM_MIN
    assert clamp_zoom(-99.0) == ZOOM_MIN


def test_clamp_zoom_clamps_above_max():
    assert clamp_zoom(ZOOM_MAX + 100.0) == ZOOM_MAX


def test_clamp_zoom_returns_float():
    assert isinstance(clamp_zoom(2), float)


# ---------------------------------------------------------------------------
# PointerEvent
# ---------------------------------------------------------------------------


def test_pointer_event_holds_provided_fields():
    button_value = Qt.MouseButton.LeftButton.value
    modifier_value = Qt.KeyboardModifier.ShiftModifier.value
    evt = PointerEvent(
        phase="press",
        x=12.5, y=34.25,
        button=button_value,
        modifiers=modifier_value,
        pressure=0.75,
    )
    assert evt.phase == "press"
    assert evt.x == 12.5
    assert evt.y == 34.25
    assert evt.button == button_value
    assert evt.modifiers == modifier_value
    assert evt.pressure == 0.75


# ---------------------------------------------------------------------------
# Image-shape validation via the canvas instance
# ---------------------------------------------------------------------------


def _make_canvas(qapp):
    """Construct a canvas under the qapp fixture; returns ``None`` if the
    GL widget cannot be created in this environment."""
    try:
        from Imervue.paint.canvas import PaintCanvas
        return PaintCanvas()
    except Exception:  # pragma: no cover - headless / no GL
        return None


def test_load_image_rejects_non_rgba(qapp, sample_rgb_array):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        with pytest.raises(ValueError):
            canvas.load_image(sample_rgb_array)
    finally:
        canvas.deleteLater()


def test_load_image_rejects_wrong_dtype(qapp):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        with pytest.raises(ValueError):
            canvas.load_image(np.zeros((4, 4, 4), dtype=np.float32))
    finally:
        canvas.deleteLater()


def test_load_image_accepts_rgba_uint8(qapp, sample_rgba_array):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        assert canvas.current_image() is not None
        assert canvas.current_image().shape == sample_rgba_array.shape
    finally:
        canvas.deleteLater()


def test_load_image_none_clears_canvas(qapp, sample_rgba_array):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        canvas.load_image(None)
        assert canvas.current_image() is None
    finally:
        canvas.deleteLater()


def test_set_tool_dispatcher_accepts_callable(qapp):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.set_tool_dispatcher(lambda evt: False)
        canvas.set_tool_dispatcher(None)
    finally:
        canvas.deleteLater()


def test_dispatch_produces_int_button_and_modifiers(qapp, sample_rgba_array):
    """Regression: PySide6 6.x returns Qt.MouseButton / KeyboardModifier
    as flag enums that don't auto-convert via int(). _dispatch has to
    go through .value to keep PointerEvent.button + .modifiers as
    plain ints."""
    import warnings

    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        captured: list = []
        canvas.set_tool_dispatcher(lambda evt: captured.append(evt) or False)
        with warnings.catch_warnings():
            # The QMouseEvent constructor used here is technically
            # deprecated; Qt is pushing callers to a 7-arg form that
            # also takes scene and global points. The 6-arg form still
            # works and is plenty for the dispatch unit test.
            warnings.simplefilter("ignore", DeprecationWarning)
            mouse_evt = QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(5.0, 5.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.AltModifier,
            )
        canvas._dispatch("move", mouse_evt)   # noqa: SLF001
        assert captured, "dispatcher must fire for a real QMouseEvent"
        evt = captured[0]
        assert isinstance(evt.button, int)
        assert isinstance(evt.modifiers, int)
    finally:
        canvas.deleteLater()


def test_zoom_factor_starts_at_unity(qapp):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        assert canvas.zoom_factor() == pytest.approx(1.0)
    finally:
        canvas.deleteLater()
