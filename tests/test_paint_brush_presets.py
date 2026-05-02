"""Tests for named brush presets and persistence."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint import brush_presets as bp
from Imervue.paint.tool_state import BrushSettings
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_brush_presets", None)
    yield
    user_setting_dict.pop("paint_brush_presets", None)


# ---------------------------------------------------------------------------
# BrushPreset construction + validation
# ---------------------------------------------------------------------------


def test_preset_construction_with_defaults():
    p = bp.BrushPreset(name="Test")
    assert p.name == "Test"
    assert p.size == 12
    assert p.opacity == pytest.approx(1.0)


def test_preset_is_frozen():
    p = bp.BrushPreset(name="Test")
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.size = 50  # type: ignore[misc]


def test_preset_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        bp.BrushPreset(name="   ")


def test_preset_rejects_unknown_kind():
    with pytest.raises(ValueError, match="kind"):
        bp.BrushPreset(name="X", kind="quill")


def test_preset_rejects_unknown_blend_mode():
    with pytest.raises(ValueError, match="blend_mode"):
        bp.BrushPreset(name="X", blend_mode="vivid_glow")


def test_preset_rejects_size_out_of_range():
    with pytest.raises(ValueError, match="size"):
        bp.BrushPreset(name="X", size=10000)


def test_preset_rejects_opacity_out_of_range():
    with pytest.raises(ValueError, match="opacity"):
        bp.BrushPreset(name="X", opacity=2.0)


def test_preset_rejects_negative_stabilizer():
    with pytest.raises(ValueError, match="stabilizer"):
        bp.BrushPreset(name="X", stabilizer=-0.5)


# ---------------------------------------------------------------------------
# from_settings / to_settings
# ---------------------------------------------------------------------------


def test_from_settings_copies_all_fields():
    settings = BrushSettings(
        kind="marker", size=24, opacity=0.7, hardness=0.5,
        density=0.8, blend_mode="multiply", stabilizer=0.3, tip_path="brushtip.png",
    )
    preset = bp.BrushPreset.from_settings("Mine", settings)
    assert preset.name == "Mine"
    assert preset.kind == "marker"
    assert preset.size == 24
    assert preset.opacity == pytest.approx(0.7)
    assert preset.tip_path == "brushtip.png"


def test_to_settings_round_trips_with_from_settings():
    settings = BrushSettings(
        kind="airbrush", size=60, opacity=0.4, hardness=0.1,
    )
    preset = bp.BrushPreset.from_settings("Mist", settings)
    assert preset.to_settings() == settings


# ---------------------------------------------------------------------------
# to_dict / from_dict
# ---------------------------------------------------------------------------


def test_round_trip_via_dict():
    p = bp.BrushPreset(
        name="Round", kind="pen", size=8, opacity=0.5,
        blend_mode="screen", tip_path="/x.png",
    )
    rebuilt = bp.BrushPreset.from_dict(p.to_dict())
    assert rebuilt == p


def test_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        bp.BrushPreset.from_dict("garbage")  # type: ignore[arg-type]


def test_from_dict_supplies_defaults_for_missing_keys():
    rebuilt = bp.BrushPreset.from_dict({"name": "Bare"})
    assert rebuilt.name == "Bare"
    assert rebuilt.size == 12


def test_from_dict_blank_tip_path_normalises_to_none():
    rebuilt = bp.BrushPreset.from_dict({"name": "X", "tip_path": ""})
    assert rebuilt.tip_path is None


# ---------------------------------------------------------------------------
# Built-in preset registry
# ---------------------------------------------------------------------------


def test_built_in_presets_have_unique_names():
    names = [p.name for p in bp.BUILT_IN_PRESETS]
    assert len(set(names)) == len(names)


def test_built_in_presets_span_multiple_kinds():
    kinds = {p.kind for p in bp.BUILT_IN_PRESETS}
    assert kinds.issuperset({"pen", "pencil", "airbrush"})


def test_find_built_in_returns_preset():
    preset = bp.find_built_in("Hard Pen")
    assert preset is not None
    assert preset.kind == "pen"
    assert preset.size == 4


def test_find_built_in_returns_none_for_unknown():
    assert bp.find_built_in("Quantum Brush") is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_and_load_round_trips():
    custom = [bp.BrushPreset(name="Mine", size=8, opacity=0.4)]
    bp.save_brush_presets(custom)
    rebuilt = bp.load_brush_presets()
    assert len(rebuilt) == 1
    assert rebuilt[0] == custom[0]


def test_load_returns_empty_list_when_nothing_stored():
    assert bp.load_brush_presets() == []


def test_load_drops_corrupt_entries():
    user_setting_dict["paint_brush_presets"] = [
        {"name": "Good", "size": 8},
        "garbage",
        {"name": "Bad blend", "blend_mode": "fake_mode"},
        {"name": "Good 2", "size": 12},
    ]
    rebuilt = bp.load_brush_presets()
    names = [p.name for p in rebuilt]
    assert names == ["Good", "Good 2"]


def test_save_empty_list_clears_storage():
    bp.save_brush_presets([bp.BrushPreset(name="Tmp")])
    bp.save_brush_presets([])
    assert bp.load_brush_presets() == []


def test_load_handles_non_list_storage():
    user_setting_dict["paint_brush_presets"] = {"oops": True}
    assert bp.load_brush_presets() == []


def test_all_presets_concatenates_builtins_and_user():
    bp.save_brush_presets([bp.BrushPreset(name="Mine")])
    presets = bp.all_presets()
    names = [p.name for p in presets]
    assert "Hard Pen" in names   # built-in
    assert "Mine" in names       # user
    # Built-ins come before user-defined.
    assert names.index("Hard Pen") < names.index("Mine")
