"""Tests for macro recording, persistence, and replay."""
from __future__ import annotations

import pytest


@pytest.fixture
def macros():
    from Imervue.macros import macro_manager as m
    # Reset the singleton between tests.
    m.manager._recording = None  # noqa: SLF001
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict.pop("macros", None)
    user_setting_dict.pop("macro_last_name", None)
    return m


class TestMacroSerialisation:
    def test_roundtrip(self, macros):
        m1 = macros.Macro(name="t", steps=[
            macros.MacroStep("set_rating", {"rating": 4}),
        ])
        m2 = macros.Macro.from_dict(m1.to_dict())
        assert m2.name == "t"
        assert len(m2.steps) == 1
        assert m2.steps[0].action == "set_rating"
        assert m2.steps[0].kwargs == {"rating": 4}

    def test_from_dict_rejects_bad_input(self, macros):
        assert macros.Macro.from_dict("bad") is None
        assert macros.Macro.from_dict({"name": 42}) is None

    def test_from_dict_skips_invalid_steps(self, macros):
        m = macros.Macro.from_dict({
            "name": "t",
            "steps": [
                {"action": "set_rating", "kwargs": {"rating": 3}},
                "garbage",
                {"action": 42},
            ],
        })
        assert len(m.steps) == 1


class TestRecording:
    def test_not_recording_by_default(self, macros):
        assert macros.manager.is_recording() is False

    def test_record_ignored_when_not_recording(self, macros):
        macros.manager.record("set_rating", rating=3)
        # Nothing saved, nothing raised.
        assert macros.manager.list_macros() == []

    def test_start_record_stop_persists(self, macros):
        macros.manager.start_recording()
        macros.manager.record("set_rating", rating=3)
        macros.manager.record("toggle_favorite", value=True)
        m = macros.manager.stop_recording("my-macro")
        assert m is not None
        assert len(m.steps) == 2
        # Reloads from storage
        all_macros = macros.manager.list_macros()
        assert len(all_macros) == 1
        assert all_macros[0].name == "my-macro"

    def test_stop_without_steps_returns_none(self, macros):
        macros.manager.start_recording()
        assert macros.manager.stop_recording("empty") is None
        assert macros.manager.list_macros() == []

    def test_unknown_action_is_dropped(self, macros):
        macros.manager.start_recording()
        macros.manager.record("totally_made_up")
        macros.manager.record("set_rating", rating=1)
        m = macros.manager.stop_recording("mixed")
        assert len(m.steps) == 1
        assert m.steps[0].action == "set_rating"


class TestReplay:
    def test_replay_set_rating_on_selection(self, macros):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        macro = macros.Macro(name="r", steps=[
            macros.MacroStep("set_rating", {"rating": 5}),
        ])
        count = macros.manager.replay(None, macro, ["/a.jpg", "/b.jpg"])
        assert count == 1
        ratings = user_setting_dict.get("image_ratings", {})
        assert ratings["/a.jpg"] == 5 and ratings["/b.jpg"] == 5

    def test_replay_clears_rating_when_zero(self, macros):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        user_setting_dict["image_ratings"] = {"/a.jpg": 3}
        macro = macros.Macro(name="r", steps=[
            macros.MacroStep("set_rating", {"rating": 0}),
        ])
        macros.manager.replay(None, macro, ["/a.jpg"])
        assert "/a.jpg" not in user_setting_dict["image_ratings"]

    def test_replay_empty_paths_noops(self, macros):
        macro = macros.Macro(name="r", steps=[
            macros.MacroStep("set_rating", {"rating": 5}),
        ])
        assert macros.manager.replay(None, macro, []) == 0

    def test_replay_continues_after_failing_step(self, macros):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        macro = macros.Macro(name="r", steps=[
            macros.MacroStep("set_rating", {"rating": "bad"}),  # cast fails
            macros.MacroStep("set_rating", {"rating": 2}),
        ])
        # One step should succeed, one should be caught/logged without crashing.
        executed = macros.manager.replay(None, macro, ["/x.jpg"])
        # Both report as "executed" (the first logged its error internally).
        assert executed >= 1
        # The second definitely set a rating.
        assert user_setting_dict.get("image_ratings", {}).get("/x.jpg") == 2


class TestDelete:
    def test_delete_macro_removes_it(self, macros):
        macros.manager.start_recording()
        macros.manager.record("set_rating", rating=1)
        macros.manager.stop_recording("to-delete")
        assert len(macros.manager.list_macros()) == 1
        macros.manager.delete_macro("to-delete")
        assert macros.manager.list_macros() == []
