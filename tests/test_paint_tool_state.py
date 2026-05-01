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


def test_set_foreground_updates_value_only_by_default():
    state = ts.load_tool_state()
    # Default ``commit=False`` updates the foreground but does NOT
    # push to recents — slider drags / live previews shouldn't
    # pollute the history with intermediate values.
    assert state.set_foreground((10, 20, 30)) is True
    assert state.foreground == (10, 20, 30)
    assert state.color_history == []


def test_set_foreground_with_commit_pushes_to_history():
    state = ts.load_tool_state()
    assert state.set_foreground((10, 20, 30), commit=True) is True
    assert state.foreground == (10, 20, 30)
    assert state.color_history[0] == (10, 20, 30)


def test_set_foreground_commit_on_same_color_still_bumps_history():
    state = ts.load_tool_state()
    state.set_foreground((10, 20, 30), commit=True)
    state.set_foreground((40, 50, 60), commit=True)
    # Re-committing (10, 20, 30) bumps it back to the front of recents.
    state.set_foreground((10, 20, 30), commit=True)
    assert state.color_history[0] == (10, 20, 30)


def test_record_foreground_in_history_pushes_current_value():
    state = ts.load_tool_state()
    state.set_foreground((10, 20, 30))   # no commit
    assert state.color_history == []
    state.record_foreground_in_history()
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
        state.set_foreground(rgb, commit=True)
    assert state.color_history[:2] == [(1, 0, 0), (2, 0, 0)]


def test_color_history_caps_at_max_entries():
    state = ts.load_tool_state()
    for i in range(ts.COLOR_HISTORY_MAX + 5):
        state.set_foreground((i, 0, 0), commit=True)
    assert len(state.color_history) == ts.COLOR_HISTORY_MAX


def test_color_history_unaffected_by_live_preview_drags():
    """Regression: dragging a colour slider triggers many
    set_foreground calls; only committed picks should land in
    the recents history."""
    state = ts.load_tool_state()
    state.set_foreground((100, 50, 25), commit=True)   # one real pick
    # Now simulate a slider drag — many set_foreground calls
    # without commit. None should push to history.
    for v in range(0, 256, 8):
        state.set_foreground((v, v, v))   # no commit kwarg
    assert state.color_history == [(100, 50, 25)]


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


def test_subscribe_receives_color_change_event():
    state = ts.load_tool_state()
    received: list[str] = []
    state.subscribe(received.append)
    state.set_foreground((9, 9, 9))
    assert ts.EVENT_COLOR in received


def test_subscribe_history_event_only_on_commit():
    """EVENT_HISTORY fires only when the change is committed —
    live-preview drags emit EVENT_COLOR but not EVENT_HISTORY."""
    state = ts.load_tool_state()
    received: list[str] = []
    state.subscribe(received.append)
    state.set_foreground((9, 9, 9))   # live preview
    assert ts.EVENT_HISTORY not in received
    state.set_foreground((20, 20, 20), commit=True)
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


# ---------------------------------------------------------------------------
# Symmetry mode
# ---------------------------------------------------------------------------


def test_default_symmetry_mode_is_off():
    state = ts.load_tool_state()
    assert state.symmetry_mode == "off"


def test_set_symmetry_mode_changes_value():
    state = ts.load_tool_state()
    assert state.set_symmetry_mode("radial_4") is True
    assert state.symmetry_mode == "radial_4"


def test_set_symmetry_mode_idempotent_returns_false():
    state = ts.load_tool_state()
    state.set_symmetry_mode("horizontal")
    assert state.set_symmetry_mode("horizontal") is False


def test_set_symmetry_mode_rejects_unknown():
    state = ts.load_tool_state()
    with pytest.raises(ValueError):
        state.set_symmetry_mode("kaleidoscope")


def test_set_symmetry_mode_emits_symmetry_event():
    state = ts.load_tool_state()
    received: list[str] = []
    state.subscribe(received.append)
    state.set_symmetry_mode("vertical")
    assert ts.EVENT_SYMMETRY in received


def test_symmetry_mode_persists_to_user_setting_dict():
    state = ts.load_tool_state()
    state.set_symmetry_mode("radial_8")
    raw = user_setting_dict.get("paint_state")
    assert raw["symmetry_mode"] == "radial_8"


def test_symmetry_mode_round_trips_via_to_from_dict():
    state = ts.load_tool_state()
    state.set_symmetry_mode("both")
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.symmetry_mode == "both"


def test_from_dict_drops_unknown_symmetry_mode():
    rebuilt = ts.ToolState.from_dict({"symmetry_mode": "kaleidoscope"})
    assert rebuilt.symmetry_mode == "off"


def test_from_dict_handles_missing_symmetry_key():
    rebuilt = ts.ToolState.from_dict({})
    assert rebuilt.symmetry_mode == "off"


# ---------------------------------------------------------------------------
# Ruler
# ---------------------------------------------------------------------------


def test_default_ruler_is_off_mode():
    state = ts.load_tool_state()
    assert state.ruler.mode == "off"


def test_set_ruler_replaces_with_new_instance():
    from Imervue.paint.rulers import Ruler
    state = ts.load_tool_state()
    new = Ruler(mode="linear", anchor=(10.0, 20.0), angle_deg=45.0)
    assert state.set_ruler(new) is True
    assert state.ruler == new


def test_set_ruler_with_kwargs_patches_fields():
    state = ts.load_tool_state()
    state.set_ruler(mode="linear", angle_deg=30.0)
    assert state.ruler.mode == "linear"
    assert state.ruler.angle_deg == 30.0


def test_set_ruler_idempotent_returns_false():
    state = ts.load_tool_state()
    state.set_ruler(mode="linear", angle_deg=45.0)
    assert state.set_ruler(mode="linear", angle_deg=45.0) is False


def test_set_ruler_rejects_unknown_mode():
    state = ts.load_tool_state()
    with pytest.raises(ValueError, match="unknown ruler mode"):
        state.set_ruler(mode="fractal")


def test_set_ruler_rejects_both_ruler_and_kwargs():
    from Imervue.paint.rulers import Ruler
    state = ts.load_tool_state()
    with pytest.raises(ValueError, match="ruler= or"):
        state.set_ruler(Ruler(mode="linear"), angle_deg=10.0)


def test_set_ruler_emits_ruler_event():
    state = ts.load_tool_state()
    received: list[str] = []
    state.subscribe(received.append)
    state.set_ruler(mode="linear")
    assert ts.EVENT_RULER in received


def test_ruler_persists_to_user_setting_dict():
    state = ts.load_tool_state()
    state.set_ruler(mode="ellipse", anchor=(100.0, 50.0), rx=20.0, ry=10.0)
    raw = user_setting_dict.get("paint_state")
    assert raw["ruler"]["mode"] == "ellipse"
    assert raw["ruler"]["anchor"] == [100.0, 50.0]


def test_ruler_round_trips_via_to_from_dict():
    state = ts.load_tool_state()
    state.set_ruler(
        mode="parallel", anchor=(5.0, 6.0), angle_deg=30.0, spacing=15.0,
    )
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.ruler.mode == "parallel"
    assert rebuilt.ruler.anchor == (5.0, 6.0)
    assert rebuilt.ruler.angle_deg == 30.0
    assert rebuilt.ruler.spacing == 15.0


def test_from_dict_handles_missing_ruler_key():
    rebuilt = ts.ToolState.from_dict({})
    assert rebuilt.ruler.mode == "off"


def test_from_dict_drops_unknown_ruler_mode():
    rebuilt = ts.ToolState.from_dict({"ruler": {"mode": "kaleidoscope"}})
    assert rebuilt.ruler.mode == "off"


# ---------------------------------------------------------------------------
# Sub-tools (per-tool named presets)
# ---------------------------------------------------------------------------


def test_sub_tools_default_to_empty():
    state = ts.load_tool_state()
    assert state.sub_tools == {}


def test_add_sub_tool_captures_current_brush():
    state = ts.load_tool_state()
    state.set_brush(size=42, opacity=0.5)
    sub_tool = state.add_sub_tool("brush", "rough-pen")
    assert sub_tool.brush.size == 42
    assert sub_tool.brush.opacity == 0.5
    assert state.list_sub_tools("brush")[0].name == "rough-pen"


def test_add_sub_tool_replaces_existing_with_same_name():
    state = ts.load_tool_state()
    state.set_brush(size=10)
    state.add_sub_tool("brush", "preset")
    state.set_brush(size=22)
    state.add_sub_tool("brush", "preset")   # same name → replace
    presets = state.list_sub_tools("brush")
    assert len(presets) == 1
    assert presets[0].brush.size == 22


def test_add_sub_tool_preserves_order_of_others():
    state = ts.load_tool_state()
    state.add_sub_tool("brush", "first")
    state.add_sub_tool("brush", "second")
    state.add_sub_tool("brush", "first")   # update-in-place must not move it
    names = [st.name for st in state.list_sub_tools("brush")]
    assert names == ["first", "second"]


def test_add_sub_tool_rejects_unknown_tool():
    state = ts.load_tool_state()
    with pytest.raises(ValueError, match="unknown tool"):
        state.add_sub_tool("not-a-tool", "preset")


def test_add_sub_tool_rejects_blank_name():
    state = ts.load_tool_state()
    with pytest.raises(ValueError, match="name"):
        state.add_sub_tool("brush", "   ")


def test_add_sub_tool_rejects_overly_long_name():
    state = ts.load_tool_state()
    long_name = "x" * (ts.SUB_TOOL_NAME_MAX_LEN + 1)
    with pytest.raises(ValueError, match="<="):
        state.add_sub_tool("brush", long_name)


def test_apply_sub_tool_swaps_active_settings():
    state = ts.load_tool_state()
    state.set_brush(size=10, opacity=0.2)
    state.add_sub_tool("brush", "soft")
    state.set_brush(size=99, opacity=1.0)
    state.set_tool("eyedropper")   # different tool — apply must switch back
    assert state.apply_sub_tool("brush", "soft") is True
    assert state.tool == "brush"
    assert state.brush.size == 10
    assert state.brush.opacity == 0.2


def test_apply_sub_tool_returns_false_for_missing_name():
    state = ts.load_tool_state()
    assert state.apply_sub_tool("brush", "ghost") is False


def test_apply_sub_tool_rejects_unknown_tool():
    state = ts.load_tool_state()
    with pytest.raises(ValueError, match="unknown tool"):
        state.apply_sub_tool("nope", "preset")


def test_remove_sub_tool_drops_entry():
    state = ts.load_tool_state()
    state.add_sub_tool("brush", "preset")
    assert state.remove_sub_tool("brush", "preset") is True
    assert state.list_sub_tools("brush") == []


def test_remove_sub_tool_returns_false_for_missing():
    state = ts.load_tool_state()
    assert state.remove_sub_tool("brush", "missing") is False


def test_remove_sub_tool_rejects_unknown_tool():
    state = ts.load_tool_state()
    with pytest.raises(ValueError, match="unknown tool"):
        state.remove_sub_tool("nope", "preset")


def test_sub_tool_emits_sub_tool_channel():
    state = ts.load_tool_state()
    seen: list[str] = []
    state.subscribe(seen.append)
    state.add_sub_tool("brush", "preset")
    assert ts.EVENT_SUB_TOOL in seen


def test_sub_tool_persists_to_user_setting_dict():
    state = ts.load_tool_state()
    state.set_brush(size=50)
    state.add_sub_tool("brush", "fifty")
    raw = user_setting_dict["paint_state"]
    assert "sub_tools" in raw
    assert raw["sub_tools"]["brush"][0]["name"] == "fifty"
    assert raw["sub_tools"]["brush"][0]["brush"]["size"] == 50


def test_sub_tools_round_trip_via_from_dict():
    state = ts.load_tool_state()
    state.set_brush(size=33)
    state.add_sub_tool("brush", "p1")
    state.set_fill(tolerance=99)
    state.add_sub_tool("fill", "p2")
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.list_sub_tools("brush")[0].brush.size == 33
    assert rebuilt.list_sub_tools("fill")[0].fill.tolerance == 99


def test_sub_tools_from_dict_drops_unknown_tool_keys():
    rebuilt = ts.ToolState.from_dict({"sub_tools": {"not-a-tool": []}})
    assert rebuilt.sub_tools == {}


def test_sub_tools_from_dict_drops_malformed_entries():
    rebuilt = ts.ToolState.from_dict({
        "sub_tools": {"brush": ["not-a-dict", {"name": ""}]},
    })
    assert rebuilt.sub_tools == {}


def test_list_sub_tools_returns_fresh_list():
    """Mutating the returned list must not affect state's internal store."""
    state = ts.load_tool_state()
    state.add_sub_tool("brush", "preset")
    listed = state.list_sub_tools("brush")
    listed.clear()
    assert len(state.list_sub_tools("brush")) == 1


def test_remove_last_sub_tool_drops_empty_bucket():
    """Removing the only entry in a tool bucket must not leave an
    empty list behind in ``sub_tools``."""
    state = ts.load_tool_state()
    state.add_sub_tool("brush", "preset")
    state.remove_sub_tool("brush", "preset")
    assert "brush" not in state.sub_tools


# ---------------------------------------------------------------------------
# Eyedropper sample-all-layers flag
# ---------------------------------------------------------------------------


def test_eyedropper_sample_all_defaults_to_false():
    state = ts.load_tool_state()
    assert state.eyedropper_sample_all_layers is False


def test_set_eyedropper_sample_all_returns_true_on_change():
    state = ts.load_tool_state()
    assert state.set_eyedropper_sample_all_layers(True) is True
    assert state.eyedropper_sample_all_layers is True


def test_set_eyedropper_sample_all_idempotent_returns_false():
    state = ts.load_tool_state()
    state.set_eyedropper_sample_all_layers(True)
    assert state.set_eyedropper_sample_all_layers(True) is False


def test_set_eyedropper_sample_all_emits_eyedropper_channel():
    state = ts.load_tool_state()
    seen: list[str] = []
    state.subscribe(seen.append)
    state.set_eyedropper_sample_all_layers(True)
    assert ts.EVENT_EYEDROPPER in seen


def test_eyedropper_sample_all_persists_to_user_setting_dict():
    state = ts.load_tool_state()
    state.set_eyedropper_sample_all_layers(True)
    raw = user_setting_dict["paint_state"]
    assert raw["eyedropper_sample_all_layers"] is True


def test_eyedropper_sample_all_round_trips_via_from_dict():
    state = ts.load_tool_state()
    state.set_eyedropper_sample_all_layers(True)
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.eyedropper_sample_all_layers is True


def test_eyedropper_sample_all_default_when_key_missing():
    rebuilt = ts.ToolState.from_dict({})
    assert rebuilt.eyedropper_sample_all_layers is False
