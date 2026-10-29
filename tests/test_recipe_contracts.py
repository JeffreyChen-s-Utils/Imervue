"""Recipe contracts at normalization, optional effects and pipeline boundaries."""
import builtins
from dataclasses import dataclass
import importlib

import numpy as np
import pytest

from Imervue.image.recipe import Recipe, STAGE_NAMES


EFFECTS = [
    ("levels", "LevelsOptions"),
    ("channel_mixer", "ChannelMixerOptions"),
    ("gradient_map", "GradientMapOptions"),
    ("lens_flare", "LensFlareOptions"),
    ("film_grain", "FilmGrainOptions"),
]


@pytest.fixture
def pixels():
    return np.arange(5 * 7 * 4, dtype=np.uint8).reshape(5, 7, 4)


@pytest.mark.parametrize("key,options_name", EFFECTS)
@pytest.mark.parametrize("failure", [ImportError, ValueError, TypeError, RuntimeError])
def test_optional_decode_errors_propagate(monkeypatch, pixels, key, options_name, failure):
    module = importlib.import_module(f"Imervue.image.{key}")
    calls = []

    def decode(_data):
        calls.append("decode")
        raise failure("decode failure")

    monkeypatch.setattr(getattr(module, options_name), "from_dict", decode)
    with pytest.raises(failure, match="decode failure"):
        Recipe(extra={"metadata": True}).apply_stages(pixels, key, key)
    assert calls == ["decode"]


@pytest.mark.parametrize("key,options_name", EFFECTS)
@pytest.mark.parametrize("failure", [ValueError, TypeError, RuntimeError])
def test_optional_apply_error_boundary(monkeypatch, pixels, caplog, key, options_name, failure):
    module = importlib.import_module(f"Imervue.image.{key}")
    marker = object()
    calls = []

    def decode(data):
        calls.append(data)
        return marker

    def apply(arr, options):
        assert arr is pixels
        assert options is marker
        raise failure("application failure")

    monkeypatch.setattr(getattr(module, options_name), "from_dict", decode)
    monkeypatch.setattr(module, f"apply_{key}", apply)
    recipe = Recipe(extra={key: {"enabled": True}})
    if failure is RuntimeError:
        with pytest.raises(RuntimeError, match="application failure"):
            recipe.apply_stages(pixels, key, key)
    else:
        assert recipe.apply_stages(pixels, key, key) is pixels
        assert "apply failed: application failure" in caplog.text
    assert calls == [{"enabled": True}]


@pytest.mark.parametrize("key,_options_name", EFFECTS)
def test_optional_import_failure_and_empty_extra(monkeypatch, pixels, key, _options_name):
    original_import = builtins.__import__
    calls = []

    def failing_import(name, *args, **kwargs):
        if name == f"Imervue.image.{key}":
            calls.append(name)
            raise ImportError("optional module unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    assert Recipe().apply_stages(pixels, key, key) is pixels
    assert calls == []
    assert Recipe(extra={"metadata": True}).apply_stages(pixels, key, key) is pixels
    assert calls == [f"Imervue.image.{key}"]


def test_threshold_retains_successful_partial_result(monkeypatch, pixels):
    from Imervue.image import posterize

    changed = pixels.copy()
    changed[..., :3] = 255
    monkeypatch.setattr(posterize, "apply_threshold", lambda _arr, _opts: changed)

    def fail(_arr, _opts):
        assert _arr is changed
        raise ValueError("posterize rejected")

    monkeypatch.setattr(posterize, "apply_posterize", fail)
    assert Recipe(extra={"metadata": True}).apply_stages(
        pixels, "threshold_posterize", "threshold_posterize"
    ) is changed


def test_lut_type_error_propagates_but_oserror_skips(monkeypatch, pixels):
    from Imervue.image import lut

    def fail(*_args, **_kwargs):
        raise TypeError("invalid lut argument")

    monkeypatch.setattr(lut, "apply_cube_lut", fail)
    recipe = Recipe(lut_path="missing.cube")
    with pytest.raises(TypeError, match="invalid lut argument"):
        recipe.apply_stages(pixels, "lut", "lut")

    def unavailable(*_args, **_kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr(lut, "apply_cube_lut", unavailable)
    assert recipe.apply_stages(pixels, "lut", "lut") is pixels


def test_normalization_and_loading_preserve_distinct_curve_contracts():
    data = {"tone_curve_rgb": [("0", "1", "ignored")]}
    assert Recipe.from_dict(data).tone_curve_rgb == [(0.0, 1.0)]
    with pytest.raises(ValueError):
        Recipe(tone_curve_rgb=data["tone_curve_rgb"]).normalized()


def test_subclass_load_and_normalize_construction_and_copy_depth():
    @dataclass
    class ExtendedRecipe(Recipe):
        version: int = 7

    nested = {"items": [1]}
    recipe = ExtendedRecipe.from_dict({"version": 9, "extra": {"nested": nested}, "future": 3})
    assert type(recipe) is ExtendedRecipe
    assert recipe.version == 9
    assert recipe.exif_oriented is False
    assert recipe.extra == {"nested": nested, "future": 3}
    normalized = recipe.normalized()
    assert type(normalized) is Recipe
    assert normalized.extra is not recipe.extra
    assert normalized.extra["nested"] is nested
    serialized = recipe.to_dict()
    assert serialized["version"] == 9
    assert serialized["extra"]["nested"] is not nested


def test_identity_bypasses_validation_and_reversed_stages_are_empty():
    invalid = np.zeros(7, dtype=float)
    assert Recipe().apply(invalid) is invalid
    with pytest.raises(ValueError, match="Recipe.apply expects HxWx4 RGBA"):
        Recipe(exposure=1).apply(invalid)
    assert Recipe(exposure=1).apply_stages(invalid, STAGE_NAMES[-1], STAGE_NAMES[0]) is invalid


def test_serialized_unknown_fields_override_nested_extra():
    recipe = Recipe.from_dict({"future": [2], "extra": {"future": [1]}, "crop": [1.9, 2, 3, 4]})
    assert recipe.extra == {"future": [2]}
    assert recipe.crop == (1, 2, 3, 4)
    assert recipe.to_dict()["crop"] == [1, 2, 3, 4]


@pytest.mark.parametrize("intensity,expected", [(float("nan"), 1.0), (-2, 0.0), (4, 1.0)])
def test_normalization_preserves_lut_clamping(intensity, expected):
    assert Recipe(lut_intensity=intensity).normalized().lut_intensity == expected


def test_normalized_recipe_hash_fixture():
    recipe = Recipe(
        rotate_steps=5, brightness=.25, crop=(1, 2, 3, 4),
        tone_curve_rgb=[(0, .1), (1, .9)], extra={"future": [1, 2]},
    )
    assert recipe.recipe_hash() == "c0210dd641c33e77"
    assert Recipe.from_dict(recipe.to_dict()).recipe_hash() == "c0210dd641c33e77"
    assert Recipe().recipe_hash() == ""
