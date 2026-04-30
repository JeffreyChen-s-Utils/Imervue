"""Tests for workspace dock-layout presets."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint import workspace_presets as wp
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_workspace_presets", None)
    yield
    user_setting_dict.pop("paint_workspace_presets", None)


# ---------------------------------------------------------------------------
# DockState
# ---------------------------------------------------------------------------


def test_dock_state_construction():
    s = wp.DockState(name="brush", area="left", order=2, size_px=300)
    assert s.name == "brush"
    assert s.order == 2


def test_dock_state_is_frozen():
    s = wp.DockState(name="brush")
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.area = "left"  # type: ignore[misc]


def test_dock_state_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        wp.DockState(name="   ")


def test_dock_state_rejects_unknown_area():
    with pytest.raises(ValueError, match="unknown dock area"):
        wp.DockState(name="brush", area="upside-down")


def test_dock_state_rejects_undersized_size():
    with pytest.raises(ValueError, match="size_px"):
        wp.DockState(name="brush", size_px=10)


def test_dock_state_rejects_oversized_size():
    with pytest.raises(ValueError, match="size_px"):
        wp.DockState(name="brush", size_px=10000)


def test_dock_state_round_trip_via_dict():
    s = wp.DockState(name="layers", area="left", order=3, size_px=320, visible=False)
    rebuilt = wp.DockState.from_dict(s.to_dict())
    assert rebuilt == s


def test_dock_state_from_dict_clamps_size_above_max():
    rebuilt = wp.DockState.from_dict({"name": "X", "size_px": 99999})
    assert rebuilt.size_px == wp.MAX_SIZE_PX


def test_dock_state_from_dict_falls_back_to_default_area():
    rebuilt = wp.DockState.from_dict({"name": "X", "area": "outer-space"})
    assert rebuilt.area == wp.DEFAULT_AREA


# ---------------------------------------------------------------------------
# WorkspacePreset
# ---------------------------------------------------------------------------


def test_workspace_preset_construction():
    p = wp.WorkspacePreset(
        name="Tiny",
        docks=(wp.DockState(name="brush"), wp.DockState(name="color")),
    )
    assert len(p.docks) == 2


def test_workspace_preset_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        wp.WorkspacePreset(name="   ", docks=())


def test_workspace_preset_rejects_duplicate_dock():
    with pytest.raises(ValueError, match="duplicate dock"):
        wp.WorkspacePreset(
            name="Bad",
            docks=(wp.DockState(name="brush"), wp.DockState(name="brush")),
        )


def test_workspace_preset_dock_lookup_by_name():
    p = wp.WorkspacePreset(
        name="L",
        docks=(wp.DockState(name="brush"),),
    )
    assert p.dock("brush") is not None
    assert p.dock("ghost") is None


def test_workspace_preset_round_trip_via_dict():
    p = wp.WorkspacePreset(
        name="P",
        docks=(
            wp.DockState(name="layers", order=0),
            wp.DockState(name="brush", order=1, area="left"),
        ),
    )
    rebuilt = wp.WorkspacePreset.from_dict(p.to_dict())
    assert rebuilt == p


def test_workspace_preset_from_dict_drops_corrupt_dock_state():
    rebuilt = wp.WorkspacePreset.from_dict({
        "name": "Mixed",
        "docks": [
            {"name": "brush"},
            "garbage",
            {"name": "color"},
            {"name": "color"},   # duplicate, dropped via first-wins
            {"name": "X", "area": "outer-space"},   # area falls back, kept
        ],
    })
    names = [d.name for d in rebuilt.docks]
    assert names == ["brush", "color", "X"]


def test_workspace_preset_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        wp.WorkspacePreset.from_dict("garbage")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Built-in registry
# ---------------------------------------------------------------------------


def test_built_in_presets_unique_names():
    names = [p.name for p in wp.BUILT_IN_PRESETS]
    assert len(set(names)) == len(names)


def test_built_in_presets_cover_expected_workflows():
    names = {p.name for p in wp.BUILT_IN_PRESETS}
    assert {"Default", "Drawing", "Comic", "Compact"} <= names


def test_built_in_default_has_layers_visible():
    default = wp.find_built_in("Default")
    assert default is not None
    layers = default.dock("layers")
    assert layers is not None
    assert layers.visible is True


def test_built_in_drawing_hides_history():
    drawing = wp.find_built_in("Drawing")
    assert drawing is not None
    history = drawing.dock("history")
    assert history is not None
    assert history.visible is False


def test_built_in_comic_shows_reference_dock():
    comic = wp.find_built_in("Comic")
    assert comic is not None
    reference = comic.dock("reference")
    assert reference is not None
    assert reference.visible is True


def test_find_built_in_returns_none_for_unknown():
    assert wp.find_built_in("Cosmic") is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trip():
    preset = wp.WorkspacePreset(
        name="Mine",
        docks=(wp.DockState(name="brush"),),
    )
    wp.save_workspace_presets([preset])
    rebuilt = wp.load_workspace_presets()
    assert len(rebuilt) == 1
    assert rebuilt[0] == preset


def test_load_returns_empty_when_nothing_stored():
    assert wp.load_workspace_presets() == []


def test_load_drops_corrupt_entries():
    user_setting_dict["paint_workspace_presets"] = [
        {"name": "Good", "docks": [{"name": "brush"}]},
        "garbage",
        # No name → from_dict yields default "preset"; still valid.
    ]
    rebuilt = wp.load_workspace_presets()
    names = [p.name for p in rebuilt]
    assert "Good" in names


def test_save_empty_clears_storage():
    wp.save_workspace_presets([wp.WorkspacePreset(name="Tmp")])
    wp.save_workspace_presets([])
    assert wp.load_workspace_presets() == []


def test_all_workspace_presets_built_ins_first():
    wp.save_workspace_presets([wp.WorkspacePreset(name="Mine")])
    presets = wp.all_workspace_presets()
    names = [p.name for p in presets]
    assert "Default" in names
    assert "Mine" in names
    assert names.index("Default") < names.index("Mine")
