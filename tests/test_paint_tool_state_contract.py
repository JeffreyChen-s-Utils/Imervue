"""Observable mutation, notification, persistence, and recovery contracts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass

import pytest

from Imervue.paint import tool_state as ts


OPERATIONS = [
    [("set_foreground", ((12, 34, 56),), {"commit": True}),
     ("set_foreground", ((12, 34, 56),), {"commit": True})],
    [("set_foreground", (None,), {"commit": True}),
     ("record_foreground_in_history", (), {})],
    [("set_brush", (), {"size": 19}), ("set_fill", (), {"gap_close_px": 4}),
     ("add_sub_tool", ("fill", "saved"), {}), ("set_brush", (), {"size": 25}),
     ("apply_sub_tool", ("fill", "saved"), {}), ("apply_sub_tool", ("fill", "saved"), {})],
    [("set_gradient", (), {"kind": "radial", "reverse": True, "repeat": "bad"})],
    [("set_brush", (), {"size": 21, "opacity": "bad"})],
    [("set_fill", (), {"tolerance": 21, "gap_close_px": "bad"})],
    [("set_brush", (), {"size": 21, "unknown": 1})],
    [("set_background", ((3, 2, 1),), {}), ("swap_colors", (), {}),
     ("reset_colors", (), {}), ("reset_colors", (), {})],
    [("add_sub_tool", ("brush", "one"), {}), ("add_sub_tool", ("brush", "two"), {}),
     ("add_sub_tool", ("brush", "one"), {}), ("remove_sub_tool", ("brush", "two"), {}),
     ("remove_sub_tool", ("brush", "one"), {}), ("remove_sub_tool", ("brush", "one"), {})],
]


def capture_operations(module, operations, initial=None):
    """Record save snapshots, callback observations, results, and failures."""
    trace = []
    with pytest.MonkeyPatch.context() as patch:
        settings = {}
        patch.setattr(module, "user_setting_dict", settings)
        patch.setattr(module, "schedule_save", lambda: trace.append(
            ("save", deepcopy(settings["paint_state"])),
        ))
        state = module.ToolState.from_dict(initial)
        state.subscribe(lambda event: trace.append(("event", event, deepcopy(state.to_dict()))))
        for name, args, kwargs in operations:
            try:
                result = getattr(state, name)(*args, **kwargs)
                trace.append(("return", asdict(result) if is_dataclass(result) else result))
            except (TypeError, ValueError) as error:
                trace.append(("error", type(error).__name__, str(error)))
            trace.append(("state", deepcopy(state.to_dict())))
    return trace


@pytest.mark.parametrize("operations", OPERATIONS)
def test_operation_trace_persists_before_notification(operations):
    trace = capture_operations(ts, operations)
    persisted = None
    for entry in trace:
        if entry[0] == "save":
            persisted = entry[1]
        if entry[0] == "event":
            assert entry[2] == persisted


def test_foreground_commit_order_and_equal_value_return():
    trace = capture_operations(ts, OPERATIONS[0])
    assert [item[1] for item in trace if item[0] == "event"] == ["color", "history", "history"]
    assert [item[1] for item in trace if item[0] == "return"] == [True, False]


def test_preset_tool_event_observes_old_brush_before_settings_events():
    trace = capture_operations(ts, OPERATIONS[2])
    events = [item for item in trace if item[0] == "event"]
    assert [item[1] for item in events[-5:]] == ["tool", "brush", "fill", "brush", "fill"]
    assert events[-5][2]["brush"]["size"] == 25
    assert events[-4][2]["brush"]["size"] == 19


def test_gradient_failure_retains_earlier_fields_without_persisting():
    trace = capture_operations(ts, OPERATIONS[3])
    assert [item[0] for item in trace] == ["error", "state"]
    assert trace[-1][1]["gradient_kind"] == "radial"
    assert trace[-1][1]["gradient_reverse"] is True
    assert trace[-1][1]["gradient_repeat"] == 1


@pytest.mark.parametrize("operations", OPERATIONS[4:7])
def test_snapshot_update_failure_is_atomic(operations):
    trace = capture_operations(ts, operations)
    assert [item[0] for item in trace] == ["error", "state"]
    assert trace[-1][1] == ts.ToolState().to_dict()


def test_listener_mutation_uses_snapshot_and_detach_is_repeatable(monkeypatch):
    monkeypatch.setattr(ts, "schedule_save", lambda: None)
    state = ts.ToolState()
    seen = []

    def first(event):
        seen.append(("first", event))
        detach_second()

    state.subscribe(first)
    detach_second = state.subscribe(lambda event: seen.append(("second", event)))
    state.set_tool("fill")
    detach_second()
    state.set_tool("brush")
    assert seen == [("first", "tool"), ("second", "tool"), ("first", "tool")]


def test_listener_failure_propagates_after_save(monkeypatch):
    monkeypatch.setattr(ts, "schedule_save", lambda: None)
    state = ts.ToolState()

    def fail(_event):
        raise RuntimeError("listener failed")

    state.subscribe(fail)
    with pytest.raises(RuntimeError, match="listener failed"):
        state.set_tool("fill")
    assert state.tool == ts.user_setting_dict["paint_state"]["tool"] == "fill"


def test_transparent_foreground_load_and_subtool_fill_encoding():
    state = ts.ToolState(foreground=None, background=None, fill=ts.FillSettings(gap_close_px=4))
    state.sub_tools["fill"] = [ts.SubTool("saved", fill=state.fill)]
    raw = state.to_dict()
    assert raw["fill"]["gap_close_px"] == 4
    assert "gap_close_px" not in raw["sub_tools"]["fill"][0]["fill"]
    loaded = ts.ToolState.from_dict(raw)
    assert loaded.foreground == (0, 0, 0)
    assert loaded.background is None
    assert loaded.sub_tools["fill"][0].fill.gap_close_px == 0


@pytest.mark.parametrize("section, field", [("brush", "size"), ("fill", "tolerance")])
def test_malformed_top_level_settings_raise_but_preset_is_dropped(section, field):
    bad = {field: "bad"}
    with pytest.raises(ValueError):
        ts.ToolState.from_dict({section: bad})
    assert ts.ToolState.from_dict({"sub_tools": {"brush": [
        {"name": "invalid", section: bad},
    ]}}).sub_tools == {}


def test_loaded_history_keeps_duplicates_until_interactive_use(monkeypatch):
    monkeypatch.setattr(ts, "schedule_save", lambda: None)
    state = ts.ToolState.from_dict({"color_history": [[1, 2, 3], [1, 2, 3]]})
    assert state.color_history == [(1, 2, 3), (1, 2, 3)]
    state.set_foreground((1, 2, 3), commit=True)
    assert state.color_history == [(1, 2, 3), (1, 2, 3)]


def test_coercion_failure_on_assignment_keeps_original_state(monkeypatch):
    monkeypatch.setattr(ts, "schedule_save", lambda: pytest.fail("unexpected persistence"))
    state = ts.ToolState()

    class FailsOnSecondConversion:
        calls = 0

        def __bool__(self):
            self.calls += 1
            if self.calls == 2:
                raise ValueError("second conversion")
            return True

    with pytest.raises(ValueError, match="second conversion"):
        state.set_pen_smooth(FailsOnSecondConversion())
    assert state.pen_smooth is False
    with pytest.raises(ValueError, match="second conversion"):
        state.set_gradient(kind="radial", reverse=FailsOnSecondConversion())
    assert state.gradient_kind == "radial"
    assert state.gradient_reverse is False


def test_same_invalid_snapshot_still_returns_false_without_validation(monkeypatch):
    monkeypatch.setattr(ts, "schedule_save", lambda: pytest.fail("unexpected persistence"))
    state = ts.ToolState(brush=ts.BrushSettings(kind="unknown"))
    assert state.set_brush(kind="unknown") is False


def test_singleton_reset_and_classmethod_preserve_identity(monkeypatch):
    monkeypatch.setattr(ts, "user_setting_dict", {"paint_state": {"tool": "fill"}})
    ts.reset_tool_state()
    try:
        first = ts.load_tool_state()
        assert ts.load_tool_state() is first
        assert first.tool == "fill"
        ts.reset_tool_state()
        assert ts.load_tool_state() is not first

        class DerivedState(ts.ToolState):
            pass

        assert type(DerivedState.from_dict({})) is DerivedState
    finally:
        ts.reset_tool_state()
