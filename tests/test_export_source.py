"""Export source: upright, recipe applied, legacy geometry kept on the stored orientation."""
from __future__ import annotations

import pytest
from PIL import Image

from Imervue.gui import export_source
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import RecipeStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    isolated = RecipeStore(store_path=tmp_path / "recipes.json")
    monkeypatch.setattr(export_source, "recipe_store", isolated)
    return isolated


def _tagged_portrait(tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "p.jpg"
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    return str(path)


def test_tagged_photo_is_exported_upright_without_the_tag(store, tmp_path):
    img = export_source.open_export_source(_tagged_portrait(tmp_path))
    assert img.size == (20, 40)
    assert img.getexif().get(0x0112) is None   # a save that kept info can't turn it again


def test_new_recipe_applies_to_the_upright_image(store, tmp_path):
    path = _tagged_portrait(tmp_path)
    store.set_for_path(path, Recipe(crop=(0, 0, 20, 10)))
    assert export_source.open_export_source(path).size == (20, 10)


def test_legacy_geometry_recipe_applies_to_the_stored_orientation(store, tmp_path):
    path = _tagged_portrait(tmp_path)
    store.set_for_path(path, Recipe.from_dict({"crop": [0, 0, 30, 20]}))
    assert export_source.open_export_source(path).size == (30, 20)


def test_untagged_photo_is_returned_as_is(store, tmp_path):
    path = tmp_path / "plain.png"
    Image.new("RGB", (7, 5)).save(path)
    assert export_source.open_export_source(str(path)).size == (7, 5)
