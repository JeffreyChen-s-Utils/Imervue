"""Tests for export presets."""
from __future__ import annotations

from PIL import Image

from Imervue.image.export_presets import builtin_presets, get_preset, square_crop


def test_builtin_presets_have_unique_keys():
    presets = builtin_presets()
    keys = [p.key for p in presets]
    assert len(keys) == len(set(keys))
    assert len(presets) >= 4


def test_builtin_presets_quality_in_range():
    for preset in builtin_presets():
        assert 1 <= preset.quality <= 100
        assert preset.max_width >= 0 and preset.max_height >= 0


def test_get_preset_hit_and_miss():
    assert get_preset("web_1600").key == "web_1600"
    assert get_preset("does_not_exist") is None


def test_instagram_preset_is_square_crop():
    preset = get_preset("instagram_1080")
    assert preset is not None
    assert preset.square_crop


def test_square_crop_landscape():
    cropped = square_crop(Image.new("RGB", (120, 60)))
    assert cropped.size == (60, 60)


def test_square_crop_portrait():
    cropped = square_crop(Image.new("RGB", (60, 120)))
    assert cropped.size == (60, 60)


def test_square_crop_already_square():
    cropped = square_crop(Image.new("RGB", (50, 50)))
    assert cropped.size == (50, 50)
