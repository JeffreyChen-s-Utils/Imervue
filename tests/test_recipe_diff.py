"""Tests for recipe diff / selective merge."""
from __future__ import annotations

import pytest

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_diff import (
    changed_fields,
    copy_active_adjustments,
    recipe_diff,
    selective_merge,
)


# ---------------------------------------------------------------------------
# recipe_diff
# ---------------------------------------------------------------------------


def test_identical_recipes_have_no_diff():
    assert recipe_diff(Recipe(), Recipe()) == {}


def test_diff_reports_old_and_new():
    diff = recipe_diff(Recipe(), Recipe(brightness=0.5))
    assert diff == {"brightness": (0.0, 0.5)}


def test_diff_reports_multiple_fields():
    base = Recipe()
    other = Recipe(exposure=1.0, temperature=-0.3, flip_h=True)
    diff = recipe_diff(base, other)
    assert set(diff) == {"exposure", "temperature", "flip_h"}
    assert diff["flip_h"] == (False, True)


def test_diff_handles_list_and_tuple_fields():
    base = Recipe()
    other = Recipe(crop=(0, 0, 10, 10), tone_curve_rgb=[(0.0, 0.1), (1.0, 0.9)])
    diff = recipe_diff(base, other)
    assert "crop" in diff
    assert "tone_curve_rgb" in diff


def test_changed_fields_sorted():
    other = Recipe(exposure=1.0, brightness=0.2)
    assert changed_fields(Recipe(), other) == ["brightness", "exposure"]


# ---------------------------------------------------------------------------
# selective_merge
# ---------------------------------------------------------------------------


def test_selective_merge_copies_only_named_fields():
    target = Recipe(brightness=0.1, contrast=0.2)
    source = Recipe(brightness=0.9, contrast=0.9, exposure=1.5)
    merged = selective_merge(target, source, ["exposure"])
    assert merged.exposure == pytest.approx(1.5)   # copied
    assert merged.brightness == pytest.approx(0.1)  # untouched
    assert merged.contrast == pytest.approx(0.2)    # untouched


def test_selective_merge_unknown_field_raises():
    with pytest.raises(ValueError, match="unknown recipe field"):
        selective_merge(Recipe(), Recipe(), ["sharpness"])


def test_selective_merge_does_not_mutate_inputs():
    target = Recipe(brightness=0.1)
    source = Recipe(brightness=0.9)
    selective_merge(target, source, ["brightness"])
    assert target.brightness == pytest.approx(0.1)
    assert source.brightness == pytest.approx(0.9)


def test_selective_merge_empty_is_copy():
    target = Recipe(brightness=0.3)
    merged = selective_merge(target, Recipe(brightness=0.9), [])
    assert merged == target


# ---------------------------------------------------------------------------
# copy_active_adjustments
# ---------------------------------------------------------------------------


def test_copy_active_adjustments_pastes_set_fields_only():
    target = Recipe(contrast=0.4)
    source = Recipe(exposure=1.0, temperature=-0.2)
    result = copy_active_adjustments(target, source)
    assert result.exposure == pytest.approx(1.0)      # set in source -> copied
    assert result.temperature == pytest.approx(-0.2)  # set in source -> copied
    assert result.contrast == pytest.approx(0.4)      # not in source -> kept


def test_copy_active_adjustments_from_identity_is_noop():
    target = Recipe(brightness=0.5, exposure=1.0)
    assert copy_active_adjustments(target, Recipe()) == target
