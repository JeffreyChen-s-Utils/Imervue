"""Tests for the canvas view-rotation API + screen→image math."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.canvas import PaintCanvas, _wrap_rotation


# ---------------------------------------------------------------------------
# _wrap_rotation
# ---------------------------------------------------------------------------


def test_wrap_rotation_preserves_canonical_value():
    assert _wrap_rotation(45.0) == pytest.approx(45.0)


def test_wrap_rotation_handles_full_turn():
    assert _wrap_rotation(360.0) == pytest.approx(0.0)


def test_wrap_rotation_negative_minus_180_lifted_to_positive_180():
    """``-180`` and ``180`` both denote the same direction; pick the
    positive boundary so a slider's labelling stays stable."""
    assert _wrap_rotation(-180.0) == pytest.approx(180.0)


def test_wrap_rotation_drift_past_360_does_not_accumulate():
    assert _wrap_rotation(720.0 + 30.0) == pytest.approx(30.0)


def test_wrap_rotation_large_negative_wraps():
    """A monotonically decreasing rotation must fall back into the
    canonical range without exposing a negative angle bigger in
    magnitude than 180°."""
    wrapped = _wrap_rotation(-540.0)
    assert -180.0 < wrapped <= 180.0


# ---------------------------------------------------------------------------
# PaintCanvas rotation API
# ---------------------------------------------------------------------------


def _canvas(qapp):
    canvas = PaintCanvas()
    canvas.new_blank_document(width=64, height=64)
    return canvas


def test_default_rotation_is_zero(qapp):
    canvas = _canvas(qapp)
    try:
        assert canvas.rotation_degrees() == 0.0
    finally:
        canvas.deleteLater()


def test_set_canvas_rotation_writes_field(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_canvas_rotation(45.0)
        assert canvas.rotation_degrees() == pytest.approx(45.0)
    finally:
        canvas.deleteLater()


def test_set_canvas_rotation_wraps(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_canvas_rotation(720.0 + 15.0)
        assert canvas.rotation_degrees() == pytest.approx(15.0)
    finally:
        canvas.deleteLater()


def test_set_canvas_rotation_idempotent_returns_silently(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_canvas_rotation(30.0)
        # Re-setting the same value must be a no-op (no exception).
        canvas.set_canvas_rotation(30.0)
        assert canvas.rotation_degrees() == pytest.approx(30.0)
    finally:
        canvas.deleteLater()


def test_set_canvas_rotation_locks_user_view(qapp):
    """Manually rotating counts as user view control — subsequent
    window resizes must not auto-fit and clobber the rotation."""
    canvas = _canvas(qapp)
    try:
        assert canvas._user_view_locked is False  # noqa: SLF001
        canvas.set_canvas_rotation(45.0)
        assert canvas._user_view_locked is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_rotation_around_centre_accumulates_delta(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_rotation_around_centre(canvas.zoom_factor(), -15.0)
        canvas.set_rotation_around_centre(canvas.zoom_factor(), -10.0)
        assert canvas.rotation_degrees() == pytest.approx(-25.0)
    finally:
        canvas.deleteLater()


def test_set_rotation_around_centre_wraps(qapp):
    canvas = _canvas(qapp)
    try:
        for _ in range(13):   # 13 × 30° = 390° → wrap to 30°
            canvas.set_rotation_around_centre(canvas.zoom_factor(), 30.0)
        assert canvas.rotation_degrees() == pytest.approx(30.0)
    finally:
        canvas.deleteLater()


def test_load_image_resets_rotation(qapp):
    """Loading a fresh image clears the previous session's rotation;
    otherwise the new content would land sideways on screen."""
    canvas = _canvas(qapp)
    try:
        canvas.set_canvas_rotation(60.0)
        canvas.load_image(None)
        assert canvas.rotation_degrees() == 0.0
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# screen→image conversion under rotation
# ---------------------------------------------------------------------------


def test_screen_to_image_identity_when_no_rotation(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.resize(200, 200)
        # Pan/zoom are reset on load_image; no rotation either.
        out = canvas._screen_to_image(50.0, 60.0)  # noqa: SLF001
        # With identity transform the screen coord IS the image coord
        # (pan_x = pan_y = 0, zoom = 1 after setting).
        canvas._zoom = 1.0  # noqa: SLF001
        canvas._pan_x = 0.0  # noqa: SLF001
        canvas._pan_y = 0.0  # noqa: SLF001
        out = canvas._screen_to_image(50.0, 60.0)  # noqa: SLF001
        assert out == pytest.approx((50.0, 60.0))
    finally:
        canvas.deleteLater()


def test_screen_to_image_under_90_rotation_swaps_axes(qapp):
    """A 90° rotation around the canvas centre maps the centre of the
    widget onto the centre of the image regardless of orientation."""
    canvas = _canvas(qapp)
    try:
        canvas.resize(200, 200)
        canvas._zoom = 1.0  # noqa: SLF001
        canvas._pan_x = 0.0  # noqa: SLF001
        canvas._pan_y = 0.0  # noqa: SLF001
        canvas.set_canvas_rotation(90.0)
        # Image is 64×64; centre is (32, 32). The unrotated screen
        # coord (32, 32) maps to image (32, 32).
        out = canvas._screen_to_image(32.0, 32.0)  # noqa: SLF001
        assert out == pytest.approx((32.0, 32.0))
    finally:
        canvas.deleteLater()


def test_screen_to_image_falls_through_when_no_document(qapp):
    """No layers → no document shape; the rotation can't pivot, so
    the helper must fall through to the identity coords."""
    canvas = PaintCanvas()
    try:
        canvas._zoom = 1.0  # noqa: SLF001
        canvas._pan_x = 0.0  # noqa: SLF001
        canvas._pan_y = 0.0  # noqa: SLF001
        canvas._rotation_deg = 45.0  # noqa: SLF001 (set without document)
        out = canvas._screen_to_image(50.0, 50.0)  # noqa: SLF001
        # Falls back to the no-rotation transform.
        assert out == (50.0, 50.0)
    finally:
        canvas.deleteLater()


def test_screen_to_image_round_trip_under_arbitrary_rotation(qapp):
    """Build a forward map (image → screen) by inverting our own
    helper and verify the round trip lands back at the input."""
    import math as _math
    canvas = _canvas(qapp)
    try:
        canvas.resize(200, 200)
        canvas._zoom = 1.0  # noqa: SLF001
        canvas._pan_x = 0.0  # noqa: SLF001
        canvas._pan_y = 0.0  # noqa: SLF001
        canvas.set_canvas_rotation(37.5)
        # Forward: image_to_screen(p) = pan + zoom * rotate(p around centre)
        h, w = canvas.document().shape
        cx, cy = w / 2.0, h / 2.0
        rad = _math.radians(37.5)
        cos_a = _math.cos(rad)
        sin_a = _math.sin(rad)
        image = (10.0, 12.0)
        dx = image[0] - cx
        dy = image[1] - cy
        screen = (
            cx + dx * cos_a - dy * sin_a,
            cy + dx * sin_a + dy * cos_a,
        )
        recovered = canvas._screen_to_image(*screen)  # noqa: SLF001
        assert recovered == pytest.approx(image, abs=1e-6)
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# View-menu integration
# ---------------------------------------------------------------------------


def test_view_menu_rotate_ccw_no_longer_short_circuits(qapp):
    """The View-menu bridge's rotate-CCW action used to log+return
    because the canvas didn't expose set_rotation_around_centre.
    With the API in place the rotation field actually changes."""
    from Imervue.paint import tool_state as ts
    from Imervue.paint.paint_workspace import PaintWorkspace
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.rotate_canvas_ccw()
        assert ws.canvas().rotation_degrees() == pytest.approx(-15.0)
        bridge.reset_canvas_rotation()
        assert ws.canvas().rotation_degrees() == 0.0
    finally:
        ws.deleteLater()


# Keep numpy import live so ruff doesn't strip it — used by sample
# array creation in adjacent tests on the canvas.
_USED_NP = np.array
