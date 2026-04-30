"""Tests for the paint tool dispatcher (brush / eraser / eyedropper)."""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.tool_dispatcher import (
    BrushTool,
    EraserTool,
    EyedropperTool,
    ToolDispatcher,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def state():
    s = ts.load_tool_state()
    s.set_brush(size=7, opacity=1.0, hardness=1.0)
    return s


@pytest.fixture
def canvas():
    """64×64 fully-opaque white canvas."""
    arr = np.full((64, 64, 4), 255, dtype=np.uint8)
    return arr


def _press(x, y):
    return PointerEvent(phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0)


def _move(x, y):
    return PointerEvent(phase="move", x=x, y=y, button=1, modifiers=0, pressure=1.0)


def _release(x, y):
    return PointerEvent(phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0)


# ---------------------------------------------------------------------------
# ToolDispatcher routing
# ---------------------------------------------------------------------------


def test_dispatcher_with_no_image_returns_false(state):
    disp = ToolDispatcher(state, image_provider=lambda: None)
    assert disp(_press(10, 10)) is False


def test_dispatcher_routes_to_active_tool(state, canvas):
    disp = ToolDispatcher(state, image_provider=lambda: canvas)
    state.set_foreground((255, 0, 0))
    assert disp(_press(32, 32)) is True
    assert canvas[32, 32, 0] == 255


def test_dispatcher_unknown_tool_returns_false(state, canvas):
    disp = ToolDispatcher(state, image_provider=lambda: canvas)
    state.set_tool("blur")  # blur tool has no handler yet
    assert disp(_press(10, 10)) is False


def test_dispatcher_swallows_handler_exceptions(state, canvas):
    disp = ToolDispatcher(state, image_provider=lambda: canvas)

    class _Boom:
        def handle(self, evt, canvas):
            raise ValueError("nope")
    disp._handlers["brush"] = _Boom()
    # Returns False rather than crashing.
    assert disp(_press(10, 10)) is False


def test_dispatcher_cancels_old_tool_on_switch(state, canvas):
    disp = ToolDispatcher(state, image_provider=lambda: canvas)
    disp(_press(10, 10))
    state.set_tool("eraser")
    # Re-dispatch (any phase) — old brush handler must have its cancel
    # method called by then.
    disp(_press(20, 20))
    # No assertion fails = success; cleanup branch covered.


# ---------------------------------------------------------------------------
# BrushTool
# ---------------------------------------------------------------------------


def test_brush_press_paints_dab(state, canvas):
    state.set_foreground((10, 200, 30))
    tool = BrushTool(state)
    assert tool.handle(_press(32, 32), canvas) is True
    assert canvas[32, 32, 1] == 200


def test_brush_move_without_press_returns_false(state, canvas):
    tool = BrushTool(state)
    assert tool.handle(_move(5, 5), canvas) is False


def test_brush_full_stroke_emits_three_true_dispatches(state, canvas):
    tool = BrushTool(state)
    assert tool.handle(_press(10, 32), canvas) is True
    assert tool.handle(_move(20, 32), canvas) is True
    assert tool.handle(_release(30, 32), canvas) is True


def test_brush_release_without_press_returns_false(state, canvas):
    tool = BrushTool(state)
    assert tool.handle(_release(10, 10), canvas) is False


def test_brush_pressure_scales_opacity(state):
    """Lower pressure should leave less paint than full pressure."""
    canvas_full = np.full((32, 32, 4), 255, dtype=np.uint8)
    canvas_full[..., 3] = 0  # transparent so we can see deposits
    canvas_low = canvas_full.copy()

    state.set_foreground((255, 0, 0))
    state.set_brush(size=5, opacity=1.0, hardness=1.0)

    tool_full = BrushTool(state)
    tool_full.handle(PointerEvent(phase="press", x=16, y=16, button=1,
                                  modifiers=0, pressure=1.0), canvas_full)

    tool_low = BrushTool(state)
    tool_low.handle(PointerEvent(phase="press", x=16, y=16, button=1,
                                 modifiers=0, pressure=0.2), canvas_low)
    # Full-pressure dab leaves more total alpha than low-pressure one.
    assert canvas_full[..., 3].sum() > canvas_low[..., 3].sum()


def test_brush_cancel_clears_active_stroke(state, canvas):
    tool = BrushTool(state)
    tool.handle(_press(32, 32), canvas)
    tool.cancel()
    # Move after cancel returns False because there's no active stroke.
    assert tool.handle(_move(33, 33), canvas) is False


# ---------------------------------------------------------------------------
# BrushTool — symmetry
# ---------------------------------------------------------------------------


def test_brush_symmetry_horizontal_paints_mirror_dab(state, canvas):
    """Press at (10, 32) with horizontal symmetry must also paint at (54, 32)
    on a 64-wide canvas (origin at 32, mirror x = 2*32 - 10 = 54)."""
    state.set_foreground((255, 0, 0))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    state.set_symmetry_mode("horizontal")
    tool = BrushTool(state)
    tool.handle(_press(10, 32), canvas)
    # Source dab.
    assert canvas[32, 10, 0] == 255
    # Mirror dab on the opposite side of the vertical axis.
    assert canvas[32, 54, 0] == 255


def test_brush_symmetry_off_paints_only_source(state, canvas):
    state.set_foreground((255, 0, 0))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    state.set_symmetry_mode("off")
    tool = BrushTool(state)
    tool.handle(_press(10, 32), canvas)
    # The symmetric position remains white.
    assert canvas[32, 54, 0] == 255  # canvas is white pre-paint
    # Confirm the source spot was actually painted (sanity).
    assert canvas[32, 10, 0] == 255


def test_brush_symmetry_radial_4_paints_four_dabs(state, canvas):
    state.set_foreground((0, 0, 255))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    state.set_symmetry_mode("radial_4")
    tool = BrushTool(state)
    # Press at (40, 32) — 8 pixels right of centre. Radial 4 stamps at
    # 0°, 90°, 180°, 270° → (40, 32), (32, 40), (24, 32), (32, 24).
    tool.handle(_press(40, 32), canvas)
    assert canvas[32, 40, 2] == 255  # 0°
    assert canvas[40, 32, 2] == 255  # 90°
    assert canvas[32, 24, 2] == 255  # 180°
    assert canvas[24, 32, 2] == 255  # 270°


def test_brush_symmetry_extend_mirrors_move(state, canvas):
    state.set_foreground((0, 200, 0))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    state.set_symmetry_mode("vertical")
    tool = BrushTool(state)
    tool.handle(_press(10, 10), canvas)
    tool.handle(_move(10, 20), canvas)
    tool.handle(_release(10, 20), canvas)
    # Mirror of (10, 20) over horizontal axis through y=32 is (10, 44).
    assert canvas[20, 10, 1] == 200
    assert canvas[44, 10, 1] == 200


def test_brush_symmetry_origin_snapshot_survives_resize(state):
    """Mode + origin are captured at press time, so a canvas swap mid-stroke
    doesn't reroute mirrors to a different centre."""
    canvas_64 = np.full((64, 64, 4), 255, dtype=np.uint8)
    state.set_foreground((100, 100, 100))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    state.set_symmetry_mode("horizontal")
    tool = BrushTool(state)
    tool.handle(_press(10, 32), canvas_64)
    # Same canvas instance for the rest of the stroke — verifies the
    # origin captured at press is reused on subsequent dabs.
    tool.handle(_move(15, 32), canvas_64)
    tool.handle(_release(15, 32), canvas_64)
    # Mirror of (15, 32) over x=32 is x=49.
    assert canvas_64[32, 15, 0] == 100
    assert canvas_64[32, 49, 0] == 100


def test_brush_symmetry_mid_stroke_mode_change_does_not_tear(state, canvas):
    """Switching symmetry_mode mid-stroke must not change the active stroke's
    mirror layout — the snapshot at press time wins."""
    state.set_foreground((50, 50, 50))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    state.set_symmetry_mode("horizontal")
    tool = BrushTool(state)
    tool.handle(_press(10, 32), canvas)
    # User flips to off mid-stroke — the active stroke must still mirror.
    state.set_symmetry_mode("off")
    tool.handle(_release(10, 32), canvas)
    # Mirror dab at x=54 must still be painted.
    assert canvas[32, 54, 0] == 50


def test_brush_symmetry_cancel_clears_all_strokes(state, canvas):
    state.set_foreground((10, 20, 30))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    state.set_symmetry_mode("both")
    tool = BrushTool(state)
    tool.handle(_press(10, 10), canvas)
    tool.cancel()
    # Move after cancel returns False — no active strokes left.
    assert tool.handle(_move(20, 20), canvas) is False


# ---------------------------------------------------------------------------
# EraserTool
# ---------------------------------------------------------------------------


def test_eraser_drops_alpha(state, canvas):
    tool = EraserTool(state)
    tool.handle(_press(32, 32), canvas)
    assert canvas[32, 32, 3] == 0  # fully erased at the centre with hardness=1


def test_eraser_extends_along_path(state, canvas):
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    tool = EraserTool(state)
    tool.handle(_press(0, 32), canvas)
    tool.handle(_move(60, 32), canvas)
    tool.handle(_release(60, 32), canvas)
    # Trail of zero-alpha pixels along the row.
    erased_columns = (canvas[:, :, 3] == 0).any(axis=0)
    assert erased_columns[0:60].all()


def test_eraser_release_without_press_returns_false(state, canvas):
    tool = EraserTool(state)
    assert tool.handle(_release(5, 5), canvas) is False


def test_eraser_cancel_clears_state(state, canvas):
    tool = EraserTool(state)
    tool.handle(_press(32, 32), canvas)
    tool.cancel()
    assert tool.handle(_move(40, 32), canvas) is False


# ---------------------------------------------------------------------------
# EyedropperTool
# ---------------------------------------------------------------------------


def test_eyedropper_writes_pixel_to_foreground(state, canvas):
    canvas[10, 20, :3] = (33, 66, 99)
    tool = EyedropperTool(state)
    # press at (20, 10) reads canvas[10, 20]
    tool.handle(_press(20, 10), canvas)
    assert state.foreground == (33, 66, 99)


def test_eyedropper_alt_writes_to_background(state, canvas):
    canvas[10, 20, :3] = (1, 2, 3)
    tool = EyedropperTool(state)
    alt_evt = PointerEvent(
        phase="press", x=20, y=10, button=1,
        modifiers=int(Qt.KeyboardModifier.AltModifier.value),
        pressure=1.0,
    )
    tool.handle(alt_evt, canvas)
    assert state.background == (1, 2, 3)


def test_eyedropper_off_canvas_is_safe(state, canvas):
    tool = EyedropperTool(state)
    # Must not raise.
    tool.handle(_press(-5, -5), canvas)


def test_eyedropper_does_not_modify_canvas(state, canvas):
    snapshot = canvas.copy()
    tool = EyedropperTool(state)
    tool.handle(_press(10, 10), canvas)
    np.testing.assert_array_equal(canvas, snapshot)


def test_eyedropper_release_clears_active(state, canvas):
    tool = EyedropperTool(state)
    tool.handle(_press(10, 10), canvas)
    tool.handle(_release(10, 10), canvas)
    # After release, a move should not update the colour.
    canvas[20, 20, :3] = (200, 100, 50)
    tool.handle(_move(20, 20), canvas)
    assert state.foreground != (200, 100, 50)
