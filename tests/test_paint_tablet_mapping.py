"""Tests for tablet button → action mapping."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint import tablet_mapping as tm
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_tablet_profiles", None)
    yield
    user_setting_dict.pop("paint_tablet_profiles", None)


# ---------------------------------------------------------------------------
# TabletBinding
# ---------------------------------------------------------------------------


def test_binding_construction():
    b = tm.TabletBinding(button_id=3, action_kind="undo")
    assert b.button_id == 3
    assert b.action_kind == "undo"


def test_binding_is_frozen():
    b = tm.TabletBinding(button_id=1, action_kind="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.button_id = 5  # type: ignore[misc]


def test_binding_rejects_negative_button_id():
    with pytest.raises(ValueError, match="button_id"):
        tm.TabletBinding(button_id=-1, action_kind="x")


def test_binding_rejects_blank_action_kind():
    with pytest.raises(ValueError, match="non-empty"):
        tm.TabletBinding(button_id=1, action_kind="   ")


def test_binding_rejects_non_dict_params():
    with pytest.raises(ValueError, match="dict"):
        tm.TabletBinding(button_id=1, action_kind="x", params="bad")  # type: ignore[arg-type]


def test_binding_round_trip_via_dict():
    b = tm.TabletBinding(
        button_id=2, action_kind="set_tool",
        params={"tool": "brush"}, label="Side",
    )
    rebuilt = tm.TabletBinding.from_dict(b.to_dict())
    assert rebuilt == b


def test_binding_from_dict_rejects_blank_kind():
    with pytest.raises(ValueError, match="non-empty"):
        tm.TabletBinding.from_dict({"button_id": 1, "action_kind": "  "})


def test_binding_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        tm.TabletBinding.from_dict("garbage")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TabletProfile
# ---------------------------------------------------------------------------


def test_profile_construction_default_empty():
    p = tm.TabletProfile(name="X")
    assert p.bindings == []


def test_profile_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        tm.TabletProfile(name="   ")


def test_profile_find_returns_binding():
    b = tm.TabletBinding(button_id=1, action_kind="x")
    p = tm.TabletProfile(name="X", bindings=[b])
    assert p.find(1) is b
    assert p.find(99) is None


def test_profile_set_binding_replaces_existing():
    p = tm.TabletProfile(name="X", bindings=[
        tm.TabletBinding(button_id=1, action_kind="undo"),
    ])
    new_binding = tm.TabletBinding(button_id=1, action_kind="redo")
    assert p.set_binding(new_binding) is True
    assert p.find(1).action_kind == "redo"


def test_profile_set_binding_appends_when_new():
    p = tm.TabletProfile(name="X")
    p.set_binding(tm.TabletBinding(button_id=2, action_kind="undo"))
    assert len(p.bindings) == 1


def test_profile_set_binding_idempotent_returns_false():
    b = tm.TabletBinding(button_id=1, action_kind="x")
    p = tm.TabletProfile(name="X", bindings=[b])
    assert p.set_binding(b) is False


def test_profile_set_binding_at_max_raises():
    p = tm.TabletProfile(name="X")
    for i in range(tm.MAX_BINDINGS_PER_PROFILE):
        p.set_binding(tm.TabletBinding(button_id=i, action_kind="x"))
    with pytest.raises(ValueError, match=str(tm.MAX_BINDINGS_PER_PROFILE)):
        p.set_binding(
            tm.TabletBinding(button_id=999, action_kind="x"),
        )


def test_profile_remove_existing_returns_true():
    p = tm.TabletProfile(name="X", bindings=[
        tm.TabletBinding(button_id=1, action_kind="x"),
    ])
    assert p.remove(1) is True
    assert p.bindings == []


def test_profile_remove_unknown_returns_false():
    p = tm.TabletProfile(name="X")
    assert p.remove(99) is False


def test_profile_round_trip_via_dict():
    p = tm.TabletProfile(name="Mine", bindings=[
        tm.TabletBinding(button_id=1, action_kind="undo"),
        tm.TabletBinding(button_id=2, action_kind="redo"),
    ])
    rebuilt = tm.TabletProfile.from_dict(p.to_dict())
    assert rebuilt.name == "Mine"
    assert len(rebuilt.bindings) == 2


def test_profile_from_dict_drops_corrupt_bindings():
    rebuilt = tm.TabletProfile.from_dict({
        "name": "Mixed",
        "bindings": [
            {"button_id": 1, "action_kind": "good"},
            "garbage",
            {"button_id": -1, "action_kind": "bad"},   # negative ID rejected
            {"button_id": 2, "action_kind": "good 2"},
        ],
    })
    kinds = [b.action_kind for b in rebuilt.bindings]
    assert kinds == ["good", "good 2"]


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------


def test_built_in_profiles_unique_names():
    names = [p.name for p in tm.BUILT_IN_PROFILES]
    assert len(set(names)) == len(names)


def test_built_in_default_includes_brush_and_eraser():
    p = tm.find_built_in("Default")
    assert p is not None
    actions = {b.action_kind for b in p.bindings}
    assert "set_tool" in actions   # brush + eraser bindings


def test_find_built_in_unknown_returns_none():
    assert tm.find_built_in("Phantom") is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trip():
    p = tm.TabletProfile(name="Mine", bindings=[
        tm.TabletBinding(button_id=1, action_kind="undo"),
    ])
    tm.save_profiles([p])
    loaded = tm.load_profiles()
    assert len(loaded) == 1
    assert loaded[0].name == "Mine"


def test_load_returns_empty_when_nothing_stored():
    assert tm.load_profiles() == []


def test_save_too_many_profiles_raises():
    too_many = [tm.TabletProfile(name=f"P{i}") for i in range(tm.MAX_PROFILES + 1)]
    with pytest.raises(ValueError, match=str(tm.MAX_PROFILES)):
        tm.save_profiles(too_many)


def test_load_drops_corrupt_profiles():
    user_setting_dict["paint_tablet_profiles"] = [
        {"name": "Good", "bindings": [{"button_id": 1, "action_kind": "x"}]},
        "garbage",
    ]
    loaded = tm.load_profiles()
    assert [p.name for p in loaded] == ["Good"]


def test_all_profiles_built_ins_first():
    tm.save_profiles([tm.TabletProfile(name="Mine")])
    profiles = tm.all_profiles()
    names = [p.name for p in profiles]
    assert "Default" in names
    assert "Mine" in names
    assert names.index("Default") < names.index("Mine")
