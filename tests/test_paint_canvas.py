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


# ---------------------------------------------------------------------------
# new_blank_document — the "open with a paintable canvas" entry point.
# ---------------------------------------------------------------------------


def test_new_blank_document_creates_active_layer(qapp):
    """Regression: a fresh PaintCanvas has no layers, so the dispatcher's
    ``image_provider`` returns ``None`` and brush strokes silently no-op
    ("下筆後沒顏色"). ``new_blank_document`` seeds a Background layer so
    painting works immediately."""
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        assert canvas.current_image() is None
        canvas.new_blank_document(width=64, height=48)
        img = canvas.current_image()
        assert img is not None
        assert img.shape == (48, 64, 4)
        assert img.dtype == np.uint8
    finally:
        canvas.deleteLater()


def test_new_blank_document_default_fill_is_opaque_white(qapp):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.new_blank_document(width=8, height=8)
        img = canvas.current_image()
        assert img is not None
        np.testing.assert_array_equal(
            img, np.full((8, 8, 4), 255, dtype=np.uint8),
        )
    finally:
        canvas.deleteLater()


def test_new_blank_document_custom_fill(qapp):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.new_blank_document(width=4, height=4, fill=(10, 20, 30, 200))
        img = canvas.current_image()
        assert img is not None
        assert tuple(img[0, 0]) == (10, 20, 30, 200)
    finally:
        canvas.deleteLater()


def test_new_blank_document_rejects_zero_size(qapp):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        with pytest.raises(ValueError, match="positive"):
            canvas.new_blank_document(width=0, height=10)
        with pytest.raises(ValueError, match="positive"):
            canvas.new_blank_document(width=10, height=-5)
    finally:
        canvas.deleteLater()


def test_new_blank_document_rejects_bad_fill(qapp):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        with pytest.raises(ValueError, match="4-tuple"):
            canvas.new_blank_document(width=4, height=4, fill=(255, 255, 255))
        with pytest.raises(ValueError, match="4-tuple"):
            canvas.new_blank_document(width=4, height=4, fill=(255, 255, 255, 999))
    finally:
        canvas.deleteLater()


def test_dispatch_pointer_routes_to_dispatcher(qapp, sample_rgba_array):
    """``_dispatch_pointer`` is the shared mouse / tablet entry point —
    both paths must reach the dispatcher with a populated PointerEvent."""
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        captured: list = []
        canvas.set_tool_dispatcher(lambda evt: captured.append(evt) or False)
        canvas._dispatch_pointer(  # noqa: SLF001
            "press",
            x_screen=10.0, y_screen=20.0,
            button=int(Qt.MouseButton.LeftButton.value),
            modifiers=0,
            pressure=0.6,
            tilt_x=0.5, tilt_y=-0.25,
        )
        assert len(captured) == 1
        evt = captured[0]
        assert evt.phase == "press"
        assert evt.pressure == pytest.approx(0.6)
        assert evt.tilt_x == pytest.approx(0.5)
        assert evt.tilt_y == pytest.approx(-0.25)
    finally:
        canvas.deleteLater()


def test_dispatch_pointer_clamps_extreme_tilt(qapp, sample_rgba_array):
    """Tilts arrive as raw degrees scaled by the tablet path; the
    PointerEvent contract says they're already in [-1, 1]. The shared
    helper must clamp out-of-range inputs so noisy hardware can't push
    downstream tools into NaN territory."""
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        captured: list = []
        canvas.set_tool_dispatcher(lambda evt: captured.append(evt) or False)
        canvas._dispatch_pointer(  # noqa: SLF001
            "move",
            x_screen=5.0, y_screen=5.0,
            button=0, modifiers=0,
            pressure=1.0,
            tilt_x=99.0, tilt_y=-99.0,
        )
        assert captured[0].tilt_x == pytest.approx(1.0)
        assert captured[0].tilt_y == pytest.approx(-1.0)
    finally:
        canvas.deleteLater()


def test_tablet_phase_map_covers_press_move_release():
    """Regression: tabletEvent must map QEvent.TabletPress / TabletMove /
    TabletRelease onto the corresponding PointerEvent phase. Without the
    map the tablet path silently dropped events ("下筆後沒顏色")."""
    from Imervue.paint.canvas import _TABLET_PHASE
    from PySide6.QtCore import QEvent
    assert _TABLET_PHASE[QEvent.Type.TabletPress] == "press"
    assert _TABLET_PHASE[QEvent.Type.TabletMove] == "move"
    assert _TABLET_PHASE[QEvent.Type.TabletRelease] == "release"


def test_reset_view_at_real_size_uses_fit_zoom(qapp, sample_rgba_array):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        canvas.resize(800, 600)
        canvas.reset_view()
        # Document is 100×80, widget 800×600 → fit is min(8.0, 7.5, 1.0)
        # = 1.0 (clamped).
        assert canvas.zoom_factor() == pytest.approx(1.0)
    finally:
        canvas.deleteLater()


def test_apply_zoom_locks_user_view(qapp, sample_rgba_array):
    """Wheel-zoom flips the user-controlled flag so subsequent window
    resizes don't blow the user's chosen zoom away."""
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        assert canvas._user_view_locked is False  # noqa: SLF001
        canvas._apply_zoom(1.5, 100.0, 100.0)  # noqa: SLF001
        assert canvas._user_view_locked is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_reset_view_clears_user_lock(qapp, sample_rgba_array):
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        canvas._apply_zoom(1.5, 100.0, 100.0)  # noqa: SLF001
        assert canvas._user_view_locked is True  # noqa: SLF001
        canvas.reset_view()
        assert canvas._user_view_locked is False  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_load_image_clears_user_lock(qapp, sample_rgba_array):
    """Loading a new image gives the user a clean view — the auto-fit
    should resume on resize until they manually wheel-zoom again."""
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.load_image(sample_rgba_array)
        canvas._apply_zoom(2.0, 50.0, 50.0)  # noqa: SLF001
        canvas.load_image(sample_rgba_array)
        assert canvas._user_view_locked is False  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_reset_view_to_fit_defers_when_widget_too_small(qapp):
    """Big-document-on-small-widget case: a 1024² seed canvas inside a
    100×30 default-laid-out widget would fit at ~0.029, below ZOOM_MIN.
    Rather than locking at the floor zoom (where a brush stroke is too
    small to see), defer the fit until the next ``resizeGL``."""
    canvas = _make_canvas(qapp)
    if canvas is None:
        pytest.skip("GL widget unavailable in this environment")
    try:
        canvas.resize(50, 50)
        canvas.new_blank_document(width=2048, height=2048)
        # raw_zoom would be 50/2048 ≈ 0.024 < ZOOM_MIN → must defer.
        assert canvas._fit_pending is True   # noqa: SLF001
        # Once the widget is given enough room, the next fit succeeds.
        canvas.resize(800, 600)
        canvas._reset_view_to_fit()  # noqa: SLF001
        assert canvas._fit_pending is False  # noqa: SLF001
        assert canvas.zoom_factor() > ZOOM_MIN
    finally:
        canvas.deleteLater()
