"""Tests for brush-preset groups (dock categorisation)."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint import brush_presets as bp
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_brush_preset_groups", None)
    yield
    user_setting_dict.pop("paint_brush_preset_groups", None)


# ---------------------------------------------------------------------------
# PresetGroup
# ---------------------------------------------------------------------------


def test_preset_group_construction():
    g = bp.PresetGroup(name="Inks", presets=(bp.BrushPreset(name="Hard Pen"),))
    assert g.name == "Inks"
    assert len(g.presets) == 1


def test_preset_group_is_frozen():
    g = bp.PresetGroup(name="X")
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.name = "Y"  # type: ignore[misc]


def test_preset_group_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        bp.PresetGroup(name="   ")


def test_preset_group_rejects_too_many_presets():
    too_many = tuple(
        bp.BrushPreset(name=f"P{i}") for i in range(bp.MAX_PRESETS_PER_GROUP + 1)
    )
    with pytest.raises(ValueError, match=str(bp.MAX_PRESETS_PER_GROUP)):
        bp.PresetGroup(name="X", presets=too_many)


def test_preset_group_round_trip_via_dict():
    g = bp.PresetGroup(
        name="Color",
        presets=(bp.BrushPreset(name="A"), bp.BrushPreset(name="B")),
    )
    rebuilt = bp.PresetGroup.from_dict(g.to_dict())
    assert rebuilt.name == "Color"
    assert [p.name for p in rebuilt.presets] == ["A", "B"]


def test_preset_group_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        bp.PresetGroup.from_dict("garbage")  # type: ignore[arg-type]


def test_preset_group_from_dict_skips_corrupt_presets():
    rebuilt = bp.PresetGroup.from_dict({
        "name": "Mixed",
        "presets": [
            {"name": "Good", "size": 8},
            "garbage",
            {"name": "Bad blend", "blend_mode": "fake_mode"},
            {"name": "Good 2", "size": 12},
        ],
    })
    names = [p.name for p in rebuilt.presets]
    assert names == ["Good", "Good 2"]


# ---------------------------------------------------------------------------
# Built-in groups
# ---------------------------------------------------------------------------


def test_built_in_groups_unique_names():
    names = [g.name for g in bp.BUILT_IN_GROUPS]
    assert len(set(names)) == len(names)


def test_built_in_groups_cover_inks_sketch_color_wash():
    names = {g.name for g in bp.BUILT_IN_GROUPS}
    assert {"Inks", "Sketch", "Color", "Wash"} <= names


def test_find_group_returns_built_in():
    g = bp.find_group("Inks")
    assert g is not None
    assert g.name == "Inks"


def test_find_group_returns_none_for_unknown():
    assert bp.find_group("Quantum") is None


def test_find_group_finds_user_defined():
    bp.save_brush_preset_groups([bp.PresetGroup(name="Mine")])
    g = bp.find_group("Mine")
    assert g is not None
    assert g.name == "Mine"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trip():
    groups = [bp.PresetGroup(
        name="Mine",
        presets=(bp.BrushPreset(name="Custom Pen", size=8),),
    )]
    bp.save_brush_preset_groups(groups)
    rebuilt = bp.load_brush_preset_groups()
    assert len(rebuilt) == 1
    assert rebuilt[0].name == "Mine"
    assert rebuilt[0].presets[0].name == "Custom Pen"


def test_load_returns_empty_when_nothing_stored():
    assert bp.load_brush_preset_groups() == []


def test_load_drops_corrupt_groups():
    user_setting_dict["paint_brush_preset_groups"] = [
        {"name": "Good", "presets": [{"name": "P"}]},
        "garbage",
        {"name": "   "},   # blank name → rejected by from_dict via name fallback…
        {"name": "Good 2", "presets": []},
    ]
    rebuilt = bp.load_brush_preset_groups()
    names = [g.name for g in rebuilt]
    assert "Good" in names
    assert "Good 2" in names


def test_save_empty_clears_storage():
    bp.save_brush_preset_groups([bp.PresetGroup(name="Tmp")])
    bp.save_brush_preset_groups([])
    assert bp.load_brush_preset_groups() == []


def test_save_too_many_groups_raises():
    too_many = [bp.PresetGroup(name=f"G{i}") for i in range(bp.MAX_GROUPS + 1)]
    with pytest.raises(ValueError, match=str(bp.MAX_GROUPS)):
        bp.save_brush_preset_groups(too_many)


def test_all_groups_built_ins_first():
    bp.save_brush_preset_groups([bp.PresetGroup(name="Mine")])
    groups = bp.all_groups()
    names = [g.name for g in groups]
    assert "Inks" in names
    assert "Mine" in names
    assert names.index("Inks") < names.index("Mine")
