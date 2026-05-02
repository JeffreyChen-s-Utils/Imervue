"""Tests for the named color palette registry + persistence."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint import color_palette as cp
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_color_palettes", None)
    yield
    user_setting_dict.pop("paint_color_palettes", None)


# ---------------------------------------------------------------------------
# Palette dataclass
# ---------------------------------------------------------------------------


def test_palette_construction():
    p = cp.Palette(name="Tiny", colors=((255, 0, 0), (0, 255, 0)))
    assert p.name == "Tiny"
    assert p.colors == ((255, 0, 0), (0, 255, 0))


def test_palette_is_frozen():
    p = cp.Palette(name="P", colors=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.name = "Q"  # type: ignore[misc]


def test_palette_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        cp.Palette(name="   ")


def test_palette_rejects_oversized_color():
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        cp.Palette(name="P", colors=((300, 0, 0),))


def test_palette_rejects_non_three_tuple():
    with pytest.raises(ValueError, match="3-tuple"):
        cp.Palette(name="P", colors=((0, 0, 0, 255),))   # type: ignore[arg-type]


def test_palette_rejects_oversized_size():
    too_many = tuple((i % 256, 0, 0) for i in range(cp.MAX_PALETTE_SIZE + 1))
    with pytest.raises(ValueError, match=str(cp.MAX_PALETTE_SIZE)):
        cp.Palette(name="P", colors=too_many)


# ---------------------------------------------------------------------------
# to_dict / from_dict
# ---------------------------------------------------------------------------


def test_palette_round_trip_via_dict():
    p = cp.Palette(name="Tiny", colors=((10, 20, 30), (200, 100, 50)))
    rebuilt = cp.Palette.from_dict(p.to_dict())
    assert rebuilt == p


def test_palette_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        cp.Palette.from_dict("garbage")  # type: ignore[arg-type]


def test_palette_from_dict_skips_corrupt_colors():
    rebuilt = cp.Palette.from_dict({
        "name": "Mixed",
        "colors": [
            [10, 20, 30],
            "not a colour",
            [255, 255, 255, 255],   # 4-tuple — skip (palettes are RGB only)
            [400, 0, 0],            # clamped to (255, 0, 0)
            [50, 50, 50],
        ],
    })
    assert rebuilt.colors == ((10, 20, 30), (255, 0, 0), (50, 50, 50))


# ---------------------------------------------------------------------------
# Built-in registry
# ---------------------------------------------------------------------------


def test_built_in_palettes_unique_names():
    names = [p.name for p in cp.BUILT_IN_PALETTES]
    assert len(set(names)) == len(names)


def test_find_built_in_returns_named_palette():
    palette = cp.find_built_in("Manga")
    assert palette is not None
    # The Manga palette is a B&W tone scale.
    rgb_groups = {tuple(set(c)) for c in palette.colors}
    assert all(len(group) == 1 for group in rgb_groups)


def test_find_built_in_returns_none_for_unknown():
    assert cp.find_built_in("Lipstick") is None


def test_pastel_palette_has_high_luma():
    palette = cp.find_built_in("Pastel")
    assert palette is not None
    for r, g, b in palette.colors:
        assert min(r, g, b) >= 180


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trip():
    cp.save_palettes([cp.Palette(name="Mine", colors=((1, 2, 3),))])
    loaded = cp.load_palettes()
    assert len(loaded) == 1
    assert loaded[0].name == "Mine"


def test_load_returns_empty_when_nothing_stored():
    assert cp.load_palettes() == []


def test_load_drops_corrupt_entries():
    user_setting_dict["paint_color_palettes"] = [
        {"name": "Good", "colors": [[10, 20, 30]]},
        "garbage",
        {"name": "Empty allowed", "colors": []},
    ]
    loaded = cp.load_palettes()
    names = [p.name for p in loaded]
    assert "Good" in names
    assert "Empty allowed" in names


def test_save_empty_clears_storage():
    cp.save_palettes([cp.Palette(name="Tmp")])
    cp.save_palettes([])
    assert cp.load_palettes() == []


def test_all_palettes_concatenates_built_ins_and_user():
    cp.save_palettes([cp.Palette(name="Mine")])
    palettes = cp.all_palettes()
    names = [p.name for p in palettes]
    assert "Standard" in names
    assert "Mine" in names
    assert names.index("Standard") < names.index("Mine")
