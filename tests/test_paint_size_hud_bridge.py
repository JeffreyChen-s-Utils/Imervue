"""Tests for the bracket-key brush-size bridge + canvas integration."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PaintCanvas
from Imervue.paint.size_hud import SizeHudState
from Imervue.paint.size_hud_bridge import (
    DEFAULT_BUMP_FRACTION,
    MIN_BUMP_PIXELS,
    adjust_brush_size,
    trigger_size_hud,
)
from Imervue.paint.tool_state import BRUSH_SIZE_MAX, BRUSH_SIZE_MIN
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# adjust_brush_size
# ---------------------------------------------------------------------------


def test_adjust_larger_grows_size():
    state = ts.load_tool_state()
    state.set_brush(size=20)
    out = adjust_brush_size(state, larger=True)
    assert out > 20
    assert state.brush.size == out


def test_adjust_smaller_shrinks_size():
    state = ts.load_tool_state()
    state.set_brush(size=20)
    out = adjust_brush_size(state, larger=False)
    assert out < 20
    assert state.brush.size == out


def test_adjust_minimum_floor():
    """A size already at BRUSH_SIZE_MIN must stay there after a
    smaller bump rather than going negative."""
    state = ts.load_tool_state()
    state.set_brush(size=BRUSH_SIZE_MIN)
    adjust_brush_size(state, larger=False)
    assert state.brush.size == BRUSH_SIZE_MIN


def test_adjust_maximum_ceiling():
    state = ts.load_tool_state()
    state.set_brush(size=BRUSH_SIZE_MAX)
    adjust_brush_size(state, larger=True)
    assert state.brush.size == BRUSH_SIZE_MAX


def test_adjust_uses_min_pixel_bump_at_small_sizes():
    """A 1-px brush bumped up by 15% rounds to 0; the helper must
    floor at MIN_BUMP_PIXELS so the user always sees a real change."""
    state = ts.load_tool_state()
    state.set_brush(size=2)
    out = adjust_brush_size(state, larger=True)
    assert out >= 2 + MIN_BUMP_PIXELS


def test_adjust_rejects_zero_fraction():
    state = ts.load_tool_state()
    state.set_brush(size=20)
    with pytest.raises(ValueError, match="fraction"):
        adjust_brush_size(state, larger=True, fraction=0.0)


def test_adjust_rejects_negative_fraction():
    state = ts.load_tool_state()
    state.set_brush(size=20)
    with pytest.raises(ValueError, match="fraction"):
        adjust_brush_size(state, larger=True, fraction=-0.1)


def test_adjust_rejects_oversized_fraction():
    state = ts.load_tool_state()
    state.set_brush(size=20)
    with pytest.raises(ValueError, match="fraction"):
        adjust_brush_size(state, larger=True, fraction=1.5)


def test_default_fraction_is_under_one():
    """A 100% bump would multiply each press; bracket-key UX assumes
    incremental change. Drift detector for the documented default."""
    assert 0.0 < DEFAULT_BUMP_FRACTION < 1.0


# ---------------------------------------------------------------------------
# trigger_size_hud
# ---------------------------------------------------------------------------


def test_trigger_size_hud_bumps_to_current_brush_size():
    state = ts.load_tool_state()
    state.set_brush(size=24)
    hud = SizeHudState()
    trigger_size_hud(state, hud, now=10.0)
    assert hud.last_size == 24
    assert hud.last_change_at == 10.0


def test_trigger_size_hud_uses_monotonic_when_no_now():
    """No explicit ``now`` falls through to time.monotonic so the
    canvas can call this from a key handler without bookkeeping."""
    state = ts.load_tool_state()
    state.set_brush(size=12)
    hud = SizeHudState()
    trigger_size_hud(state, hud)
    assert hud.last_change_at is not None


# ---------------------------------------------------------------------------
# Canvas wiring
# ---------------------------------------------------------------------------


def test_canvas_set_size_hud_stashes_refs(qapp):
    canvas = PaintCanvas()
    state = ts.load_tool_state()
    hud = SizeHudState()
    try:
        canvas.set_size_hud(hud, state)
        assert canvas._size_hud is hud   # noqa: SLF001
        assert canvas._tool_state_for_hud is state   # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_canvas_default_has_no_hud(qapp):
    canvas = PaintCanvas()
    try:
        assert canvas._size_hud is None   # noqa: SLF001
        assert canvas._tool_state_for_hud is None   # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_workspace_canvas_has_size_hud_wired(qapp):
    """Sanity check that the workspace pushes its SizeHudState into
    the canvas after construction."""
    from Imervue.paint.paint_workspace import PaintWorkspace
    ws = PaintWorkspace()
    try:
        assert ws.canvas()._size_hud is ws._size_hud   # noqa: SLF001
    finally:
        ws.deleteLater()
