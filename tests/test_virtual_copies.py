"""Tests for virtual copies / named recipe variants in RecipeStore."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import RecipeStore


@pytest.fixture
def store(tmp_path):
    return RecipeStore(store_path=tmp_path / "recipes.json")


@pytest.fixture
def image_path(tmp_path):
    p = tmp_path / "image.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(str(p))
    return str(p)


class TestVariantLifecycle:
    def test_list_is_empty_initially(self, store, image_path):
        assert store.list_variants_for_path(image_path) == []

    def test_save_and_list(self, store, image_path):
        store.save_variant_for_path(
            image_path, "Black & White", Recipe(saturation=-1.0),
        )
        assert store.list_variants_for_path(image_path) == ["Black & White"]

    def test_get_round_trips(self, store, image_path):
        store.save_variant_for_path(
            image_path, "Cool", Recipe(temperature=-0.5),
        )
        got = store.get_variant_for_path(image_path, "Cool")
        assert got is not None
        assert got.temperature == pytest.approx(-0.5)

    def test_delete_removes_entry(self, store, image_path):
        store.save_variant_for_path(image_path, "X", Recipe(exposure=0.5))
        store.delete_variant_for_path(image_path, "X")
        assert store.list_variants_for_path(image_path) == []

    def test_rename_preserves_recipe(self, store, image_path):
        store.save_variant_for_path(image_path, "Old", Recipe(brightness=0.3))
        assert store.rename_variant_for_path(image_path, "Old", "New")
        assert store.list_variants_for_path(image_path) == ["New"]
        got = store.get_variant_for_path(image_path, "New")
        assert got is not None
        assert got.brightness == pytest.approx(0.3)

    def test_rename_fails_when_target_exists(self, store, image_path):
        store.save_variant_for_path(image_path, "A", Recipe(brightness=0.1))
        store.save_variant_for_path(image_path, "B", Recipe(brightness=0.2))
        assert store.rename_variant_for_path(image_path, "A", "B") is False

    def test_rename_fails_for_unknown_source(self, store, image_path):
        assert store.rename_variant_for_path(image_path, "Ghost", "New") is False

    def test_multiple_variants_sorted(self, store, image_path):
        store.save_variant_for_path(image_path, "Zed", Recipe(brightness=0.1))
        store.save_variant_for_path(image_path, "Alpha", Recipe(brightness=0.1))
        store.save_variant_for_path(image_path, "Mike", Recipe(brightness=0.1))
        assert store.list_variants_for_path(image_path) == ["Alpha", "Mike", "Zed"]


class TestVariantsSurviveMasterReset:
    def test_reset_master_keeps_variants(self, store, image_path):
        store.set_for_path(image_path, Recipe(brightness=0.4))
        store.save_variant_for_path(image_path, "Warm", Recipe(temperature=0.3))
        store.set_for_path(image_path, Recipe())  # reset to identity
        assert store.list_variants_for_path(image_path) == ["Warm"]
        assert store.get_for_path(image_path) is None or \
               store.get_for_path(image_path).is_identity()

    def test_variants_round_trip_across_instances(self, tmp_path, image_path):
        store1 = RecipeStore(store_path=tmp_path / "r.json")
        store1.save_variant_for_path(image_path, "V1", Recipe(saturation=-0.5))
        store1.save_variant_for_path(image_path, "V2", Recipe(saturation=0.5))

        store2 = RecipeStore(store_path=tmp_path / "r.json")
        assert store2.list_variants_for_path(image_path) == ["V1", "V2"]
        v1 = store2.get_variant_for_path(image_path, "V1")
        assert v1 is not None and v1.saturation == pytest.approx(-0.5)
