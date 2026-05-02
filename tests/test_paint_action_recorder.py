"""Tests for the action recorder + macro replay."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint.action_recorder import (
    Action,
    ActionRecorder,
    ActionRecording,
    MAX_ACTIONS_PER_RECORDING,
    MAX_RECORDINGS,
    load_recordings,
    replay,
    save_recordings,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_action_recordings", None)
    yield
    user_setting_dict.pop("paint_action_recordings", None)


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------


def test_action_construction_with_defaults():
    a = Action(kind="set_brush_size")
    assert a.kind == "set_brush_size"
    assert a.params == {}
    assert a.timestamp == pytest.approx(0.0)


def test_action_is_frozen():
    a = Action(kind="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.kind = "y"  # type: ignore[misc]


def test_action_rejects_blank_kind():
    with pytest.raises(ValueError, match="non-empty"):
        Action(kind="   ")


def test_action_rejects_non_dict_params():
    with pytest.raises(ValueError, match="dict"):
        Action(kind="x", params="bad")  # type: ignore[arg-type]


def test_action_round_trip_via_dict():
    a = Action(kind="paint_dab", params={"x": 10, "y": 20}, timestamp=1.5)
    rebuilt = Action.from_dict(a.to_dict())
    assert rebuilt == a


def test_action_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        Action.from_dict("garbage")  # type: ignore[arg-type]  # NOSONAR — intentional negative-path test


def test_action_from_dict_rejects_blank_kind():
    with pytest.raises(ValueError, match="non-empty"):
        Action.from_dict({"kind": "   "})


# ---------------------------------------------------------------------------
# ActionRecording
# ---------------------------------------------------------------------------


def test_recording_construction_with_defaults():
    r = ActionRecording(name="Test")
    assert r.name == "Test"
    assert r.actions == []


def test_recording_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        ActionRecording(name="   ")


def test_recording_append_adds_action():
    r = ActionRecording(name="T")
    assert r.append(Action(kind="x")) is True
    assert len(r.actions) == 1


def test_recording_append_caps_at_max():
    r = ActionRecording(name="T")
    r.actions = [Action(kind="x")] * MAX_ACTIONS_PER_RECORDING
    assert r.append(Action(kind="x")) is False


def test_recording_round_trip_via_dict():
    r = ActionRecording(
        name="T",
        actions=[
            Action(kind="press", params={"x": 1, "y": 2}),
            Action(kind="move", params={"x": 3, "y": 4}),
        ],
    )
    rebuilt = ActionRecording.from_dict(r.to_dict())
    assert rebuilt.name == "T"
    assert len(rebuilt.actions) == 2
    assert rebuilt.actions[0].kind == "press"


def test_recording_from_dict_drops_corrupt_actions():
    rebuilt = ActionRecording.from_dict({
        "name": "Mixed",
        "actions": [
            {"kind": "good"},
            "garbage",
            {"kind": "   "},   # blank kind → rejected
            {"kind": "good 2", "params": {"a": 1}},
        ],
    })
    kinds = [a.kind for a in rebuilt.actions]
    assert kinds == ["good", "good 2"]


# ---------------------------------------------------------------------------
# ActionRecorder
# ---------------------------------------------------------------------------


def test_recorder_starts_inactive():
    r = ActionRecorder()
    assert r.is_recording is False


def test_recorder_start_then_stop_returns_recording():
    r = ActionRecorder()
    r.start("Macro")
    rec = r.stop()
    assert rec is not None
    assert rec.name == "Macro"


def test_recorder_record_while_inactive_returns_false():
    r = ActionRecorder()
    assert r.record("x", {}) is False


def test_recorder_record_while_active_appends():
    r = ActionRecorder()
    r.start("M")
    assert r.record("press", {"x": 1}) is True
    assert r.record("move", {"x": 2}) is True
    rec = r.stop()
    assert rec is not None
    assert [a.kind for a in rec.actions] == ["press", "move"]


def test_recorder_double_start_raises():
    r = ActionRecorder()
    r.start("First")
    with pytest.raises(RuntimeError, match="already recording"):
        r.start("Second")


def test_recorder_stop_when_not_recording_returns_none():
    r = ActionRecorder()
    assert r.stop() is None


def test_recorder_timestamps_are_monotonic():
    r = ActionRecorder()
    r.start("M")
    r.record("a", {})
    r.record("b", {})
    rec = r.stop()
    assert rec is not None
    assert rec.actions[0].timestamp <= rec.actions[1].timestamp


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------


def test_replay_invokes_target_per_action():
    recording = ActionRecording(name="M", actions=[
        Action(kind="press", params={"x": 1}),
        Action(kind="move", params={"x": 2}),
        Action(kind="release", params={"x": 3}),
    ])
    calls: list[tuple[str, dict]] = []

    def target(kind, params):
        calls.append((kind, params))

    count = replay(recording, target)
    assert count == 3
    assert calls == [("press", {"x": 1}), ("move", {"x": 2}), ("release", {"x": 3})]


def test_replay_with_filter_skips_other_kinds():
    recording = ActionRecording(name="M", actions=[
        Action(kind="press"),
        Action(kind="move"),
        Action(kind="release"),
    ])
    calls: list[str] = []
    count = replay(
        recording, lambda kind, _: calls.append(kind),
        kinds_filter=("move",),
    )
    assert count == 1
    assert calls == ["move"]


def test_replay_passes_independent_param_copy():
    recording = ActionRecording(name="M", actions=[
        Action(kind="x", params={"v": 1}),
    ])
    captured: list[dict] = []

    def target(kind, params):
        captured.append(params)

    replay(recording, target)
    captured[0]["v"] = 999
    # Mutating the captured dict should not change the original.
    assert recording.actions[0].params["v"] == 1


def test_replay_propagates_target_exception():
    recording = ActionRecording(name="M", actions=[
        Action(kind="x"), Action(kind="y"),
    ])

    def target(kind, _):
        if kind == "y":
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        replay(recording, target)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trips_recordings():
    recs = [ActionRecording(name="M1", actions=[Action(kind="x")])]
    save_recordings(recs)
    loaded = load_recordings()
    assert len(loaded) == 1
    assert loaded[0].name == "M1"


def test_load_returns_empty_when_nothing_stored():
    assert load_recordings() == []


def test_save_too_many_recordings_raises():
    too_many = [ActionRecording(name=f"R{i}") for i in range(MAX_RECORDINGS + 1)]
    with pytest.raises(ValueError, match=str(MAX_RECORDINGS)):
        save_recordings(too_many)


def test_load_drops_corrupt_recordings():
    user_setting_dict["paint_action_recordings"] = [
        {"name": "Good", "actions": [{"kind": "x"}]},
        "garbage",
        {"name": "   ", "actions": []},
    ]
    loaded = load_recordings()
    names = [r.name for r in loaded]
    assert "Good" in names
