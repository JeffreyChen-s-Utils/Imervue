"""Tests for the first-run brush preset seeder."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.default_brush_presets import (
    BrushPresetSpec,
    default_brush_presets,
    seed_default_brush_presets,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def test_default_preset_catalogue_is_well_formed():
    presets = default_brush_presets()
    assert len(presets) >= 12
    # Names are unique so the seeder can use them as keys directly.
    names = [p.name for p in presets]
    assert len(set(names)) == len(names)
    # Every entry is a frozen dataclass spec with valid fields.
    for preset in presets:
        assert isinstance(preset, BrushPresetSpec)
        assert preset.name.strip()
        assert preset.settings.kind in ts.BRUSH_KINDS
        assert ts.BRUSH_SIZE_MIN <= preset.settings.size <= ts.BRUSH_SIZE_MAX
        assert 0.0 <= preset.settings.opacity <= 1.0
        assert 0.0 <= preset.settings.hardness <= 1.0


def test_seeder_populates_empty_brush_registry():
    state = ts.load_tool_state()
    assert not state.sub_tools.get("brush")
    count = seed_default_brush_presets(state)
    presets = default_brush_presets()
    assert count == len(presets)
    saved = state.list_sub_tools("brush")
    assert [s.name for s in saved] == [p.name for p in presets]


def test_seeder_is_idempotent_when_user_has_presets():
    state = ts.load_tool_state()
    state.add_sub_tool("brush", "user-favourite")
    count = seed_default_brush_presets(state)
    assert count == 0
    saved = state.list_sub_tools("brush")
    # The user's manual entry survives untouched.
    assert [s.name for s in saved] == ["user-favourite"]


def test_seeder_does_not_perturb_live_brush_settings():
    state = ts.load_tool_state()
    state.set_brush(size=99, opacity=0.42, hardness=0.13)
    before = state.brush
    seed_default_brush_presets(state)
    # Live brush is exactly what the user had before the seed pass.
    assert state.brush == before


def test_seeder_settings_round_trip_via_apply_sub_tool():
    """Applying a seeded preset must reproduce the catalogue snapshot."""
    state = ts.load_tool_state()
    seed_default_brush_presets(state)
    target = next(
        p for p in default_brush_presets() if p.name == "Sumi calligraphy"
    )
    assert state.apply_sub_tool("brush", target.name) is True
    assert state.brush == target.settings
