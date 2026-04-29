"""Tests for the Qt-free paint tool-state model."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Defaults & singleton
# ---------------------------------------------------------------------------


def test_default_state_matches_documented_defaults():
    state = ts.load_tool_state()
    assert state.tool == ts.DEFAULT_TOOL
    assert state.foreground == ts.DEFAULT_FG
    assert state.background == ts.DEFAULT_BG
    assert state.brush.kind == ts.DEFAULT_BRUSH_KIND
    assert state.brush.blend_mode == ts.DEFAULT_BLEND_MODE
    assert state.color_history == []


def test_load_returns_singleton():
    a = ts.load_tool_state()
    b = ts.load_tool_state()
    assert a is b


# ---------------------------------------------------------------------------
# Tool selection
# ---------------------------------------------------------------------------


def test_set_tool_changes_active_tool():
    state = ts.load_tool_state()
    assert state.set_tool("eraser") is True
    assert state.tool == "eraser"


def test_set_tool_idempotent_returns_false():
    state = ts.load_tool_state()
    state.set_tool("eraser")
    assert state.set_tool("eraser") is False


def test_set_tool_rejects_unknown():
    state = ts.load_tool_state()
    with pytest.raises(ValueError):
        state.set_tool("teleporter")


# ---------------------------------------------------------------------------
# Foreground / background / swap / reset
# ---------------------------------------------------------------------------


def test_set_foreground_updates_value_and_history():
    state = ts.load_tool_state()
    assert state.set_foreground((10, 20, 30)) is True
    assert state.foreground == (10, 20, 30)
    assert state.color_history[0] == (10, 20, 30)


def test_set_foreground_clamps_out_of_range_components():
    state = ts.load_tool_state()
    state.set_foreground((-50, 999, 128))
    assert state.foreground == (0, 255, 128)


def test_set_foreground_idempotent_returns_false():
    state = ts.load_tool_state()
    state.set_foreground((10, 20, 30))
    assert state.set_foreground((10, 20, 30)) is False


def test_set_background_does_not_touch_color_history():
    state = ts.load_tool_state()
    state.set_background((10, 20, 30))
    assert state.color_history == []


def test_swap_colors_exchanges_foreground_and_background():
    state = ts.load_tool_state()
    state.set_foreground((255, 0, 0))
    state.set_background((0, 0, 255))
    state.swap_colors()
    assert state.foreground == (0, 0, 255)
    assert state.background == (255, 0, 0)


def test_swap_colors_when_equal_is_noop():
    state = ts.load_tool_state()
    state.set_foreground((50, 50, 50))
    state.set_background((50, 50, 50))
    state.swap_colors()
    assert state.foreground == (50, 50, 50)


def test_reset_colors_returns_to_black_white():
    state = ts.load_tool_state()
    state.set_foreground((5, 5, 5))
    state.set_background((100, 100, 100))
    state.reset_colors()
    assert state.foreground == ts.DEFAULT_FG
    assert state.background == ts.DEFAULT_BG


# ---------------------------------------------------------------------------
# Brush settings
# ---------------------------------------------------------------------------


def test_set_brush_updates_one_attribute():
    state = ts.load_tool_state()
    assert state.set_brush(size=42) is True
    assert state.brush.size == 42


def test_set_brush_can_update_multiple_attributes():
    state = ts.load_tool_state()
    state.set_brush(size=80, opacity=0.5, hardness=0.25, blend_mode="multiply")
    assert state.brush.size == 80
    assert state.brush.opacity == 0.5
    assert state.brush.hardness == 0.25
    assert state.brush.blend_mode == "multiply"


def test_set_brush_clamps_size_above_max():
    state = ts.load_tool_state()
    state.set_brush(size=ts.BRUSH_SIZE_MAX + 1000)
    assert state.brush.size == ts.BRUSH_SIZE_MAX


def test_set_brush_clamps_opacity_below_min():
    state = ts.load_tool_state()
    state.set_brush(opacity=-3.0)
    assert state.brush.opacity == ts.BRUSH_OPACITY_MIN


def test_set_brush_rejects_unknown_attribute():
    state = ts.load_tool_state()
    with pytest.raises(ValueError):
        state.set_brush(thickness=99)


def test_set_brush_rejects_unknown_kind():
    state = ts.load_tool_state()
    with pytest.raises(ValueError):
        state.set_brush(kind="quill-pen")


def test_set_brush_rejects_unknown_blend_mode():
    state = ts.load_tool_state()
    with pytest.raises(ValueError):
        state.set_brush(blend_mode="vivid_glow")


def test_set_brush_idempotent_returns_false():
    state = ts.load_tool_state()
    state.set_brush(size=42)
    assert state.set_brush(size=42) is False


# ---------------------------------------------------------------------------
# Color history behaviour
# ---------------------------------------------------------------------------


def test_color_history_dedupes_recent_picks():
    state = ts.load_tool_state()
    for rgb in [(1, 0, 0), (2, 0, 0), (1, 0, 0)]:
        state.set_foreground(rgb)
    assert state.color_history[:2] == [(1, 0, 0), (2, 0, 0)]


def test_color_history_caps_at_max_entries():
    state = ts.load_tool_state()
    for i in range(ts.COLOR_HISTORY_MAX + 5):
        state.set_foreground((i, 0, 0))
    assert len(state.color_history) == ts.COLOR_HISTORY_MAX


def test_clear_color_history_empties_list():
    state = ts.load_tool_state()
    state.set_foreground((1, 2, 3))
    state.clear_color_history()
    assert state.color_history == []


# ---------------------------------------------------------------------------
# Listener subscription
# ---------------------------------------------------------------------------


def test_subscribe_receives_tool_change():
    state = ts.load_tool_state()
    received: list[str] = []
    state.subscribe(received.append)
    state.set_tool("fill")
    assert ts.EVENT_TOOL in received


def test_subscribe_receives_color_change_and_history_event():
    state = ts.load_tool_state()
    received: list[str] = []
    state.subscribe(received.append)
    state.set_foreground((9, 9, 9))
    assert ts.EVENT_COLOR in received
    assert ts.EVENT_HISTORY in received


def test_unsubscribe_stops_notifications():
    state = ts.load_tool_state()
    received: list[str] = []
    detach = state.subscribe(received.append)
    detach()
    state.set_tool("fill")
    assert received == []


# ---------------------------------------------------------------------------
# Persistence / round-trip
# ---------------------------------------------------------------------------


def test_state_persists_to_user_setting_dict():
    state = ts.load_tool_state()
    state.set_tool("eraser")
    state.set_foreground((10, 20, 30))
    state.set_brush(size=64, opacity=0.5)
    raw = user_setting_dict.get("paint_state")
    assert raw["tool"] == "eraser"
    assert raw["foreground"] == [10, 20, 30]
    assert raw["brush"]["size"] == 64


def test_state_round_trips_via_to_from_dict():
    state = ts.load_tool_state()
    state.set_tool("fill")
    state.set_foreground((9, 8, 7))
    state.set_background((6, 5, 4))
    state.set_brush(kind="marker", size=80, blend_mode="multiply")
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.tool == "fill"
    assert rebuilt.foreground == (9, 8, 7)
    assert rebuilt.background == (6, 5, 4)
    assert rebuilt.brush.kind == "marker"
    assert rebuilt.brush.size == 80
    assert rebuilt.brush.blend_mode == "multiply"


def test_from_dict_handles_missing_dict():
    rebuilt = ts.ToolState.from_dict(None)
    assert rebuilt.tool == ts.DEFAULT_TOOL


def test_from_dict_drops_unknown_tool():
    rebuilt = ts.ToolState.from_dict({"tool": "lightsaber"})
    assert rebuilt.tool == ts.DEFAULT_TOOL


def test_from_dict_recovers_from_corrupt_color_history():
    rebuilt = ts.ToolState.from_dict({
        "color_history": ["bogus", [1, 2], [10, 20, 30], [-5, 999, 1000], None],
    })
    assert rebuilt.color_history == [(10, 20, 30), (0, 255, 255)]
