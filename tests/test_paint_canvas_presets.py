"""Tests for the canvas-preset registry and conversion helpers."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint import canvas_presets as cp
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_canvas_presets", None)
    yield
    user_setting_dict.pop("paint_canvas_presets", None)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def test_mm_to_pixels_rounds_to_nearest_int():
    # A4 width: 210 mm at 300 dpi → 2480.31 px → 2480.
    assert cp.mm_to_pixels(210, 300) == 2480


def test_mm_to_pixels_zero_input_returns_zero():
    assert cp.mm_to_pixels(0, 300) == 0


def test_mm_to_pixels_rejects_zero_dpi():
    with pytest.raises(ValueError, match="dpi"):
        cp.mm_to_pixels(100, 0)


def test_inches_to_pixels_at_300dpi():
    assert cp.inches_to_pixels(8.5, 300) == 2550


def test_inches_to_pixels_rejects_negative_dpi():
    with pytest.raises(ValueError, match="dpi"):
        cp.inches_to_pixels(8.5, -300)


# ---------------------------------------------------------------------------
# CanvasPreset dataclass
# ---------------------------------------------------------------------------


def test_canvas_preset_construction():
    p = cp.CanvasPreset("Custom", 1024, 768, dpi=96, category="screen")
    assert p.name == "Custom"
    assert p.width_px == 1024
    assert p.height_px == 768
    assert p.dpi == 96
    assert p.category == "screen"


def test_canvas_preset_is_frozen():
    p = cp.CanvasPreset("X", 100, 100)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.name = "Y"  # type: ignore[misc]


def test_canvas_preset_rejects_zero_width():
    with pytest.raises(ValueError, match="width_px"):
        cp.CanvasPreset("X", 0, 100)


def test_canvas_preset_rejects_oversized_height():
    with pytest.raises(ValueError, match="height_px"):
        cp.CanvasPreset("X", 100, cp.MAX_DIMENSION_PX + 1)


def test_canvas_preset_rejects_zero_dpi():
    with pytest.raises(ValueError, match="dpi"):
        cp.CanvasPreset("X", 100, 100, dpi=0)


def test_canvas_preset_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        cp.CanvasPreset("   ", 100, 100)


# ---------------------------------------------------------------------------
# to_dict / from_dict
# ---------------------------------------------------------------------------


def test_canvas_preset_round_trips_via_dict():
    p = cp.CanvasPreset("Round", 500, 400, dpi=96, category="custom")
    rebuilt = cp.CanvasPreset.from_dict(p.to_dict())
    assert rebuilt == p


def test_canvas_preset_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="must be a dict"):
        cp.CanvasPreset.from_dict("not a dict")  # type: ignore[arg-type]


def test_canvas_preset_from_dict_supplies_defaults_for_missing_keys():
    rebuilt = cp.CanvasPreset.from_dict({"width_px": 800, "height_px": 600})
    assert rebuilt.width_px == 800
    assert rebuilt.height_px == 600
    assert rebuilt.dpi == 72
    assert rebuilt.category == "custom"


# ---------------------------------------------------------------------------
# Built-in preset list
# ---------------------------------------------------------------------------


def test_built_in_preset_names_unique():
    names = [p.name for p in cp.BUILT_IN_PRESETS]
    assert len(set(names)) == len(names)


def test_a4_portrait_preset_uses_300dpi():
    preset = cp.find_preset("A4 Portrait (300dpi)")
    assert preset is not None
    assert preset.width_px == 2480
    assert preset.height_px == 3508
    assert preset.dpi == 300


def test_built_in_categories_present():
    cats = {p.category for p in cp.BUILT_IN_PRESETS}
    assert "paper" in cats
    assert "manga" in cats
    assert "screen" in cats


def test_find_preset_returns_none_for_unknown():
    assert cp.find_preset("Non-existent") is None


def test_preset_names_returns_all_built_ins():
    assert len(cp.preset_names()) == len(cp.BUILT_IN_PRESETS)


def test_presets_in_category_filters_by_field():
    paper = cp.presets_in_category("paper")
    assert paper
    assert all(p.category == "paper" for p in paper)


# ---------------------------------------------------------------------------
# Custom preset persistence
# ---------------------------------------------------------------------------


def test_save_then_load_custom_presets_round_trips():
    custom = [cp.CanvasPreset("My Custom", 600, 800)]
    cp.save_custom_presets(custom)
    rebuilt = cp.load_custom_presets()
    assert len(rebuilt) == 1
    assert rebuilt[0] == custom[0]


def test_load_custom_presets_returns_empty_list_when_none_stored():
    assert cp.load_custom_presets() == []


def test_load_custom_presets_drops_corrupt_entries():
    user_setting_dict["paint_canvas_presets"] = [
        {"name": "Good", "width_px": 100, "height_px": 100, "dpi": 72, "category": "custom"},
        "garbage string",
        {"name": "Bad width", "width_px": -1, "height_px": 100},
        {"name": "Good 2", "width_px": 200, "height_px": 200, "dpi": 72, "category": "custom"},
    ]
    rebuilt = cp.load_custom_presets()
    names = [p.name for p in rebuilt]
    assert names == ["Good", "Good 2"]


def test_save_empty_list_clears_storage():
    cp.save_custom_presets([cp.CanvasPreset("Tmp", 100, 100)])
    cp.save_custom_presets([])
    assert cp.load_custom_presets() == []


def test_load_custom_presets_handles_non_list_storage():
    user_setting_dict["paint_canvas_presets"] = {"not": "a list"}
    assert cp.load_custom_presets() == []
