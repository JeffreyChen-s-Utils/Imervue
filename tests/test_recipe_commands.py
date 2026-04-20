"""Tests for EditRecipeCommand (non-destructive recipe undo/redo)."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.gpu_image_view.actions import recipe_commands
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import RecipeStore
from Imervue.image import recipe_store as recipe_store_mod


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Swap the module-level singleton for a per-test RecipeStore."""
    fresh = RecipeStore(store_path=tmp_path / "recipes.json")
    monkeypatch.setattr(recipe_store_mod, "recipe_store", fresh)
    monkeypatch.setattr(recipe_commands, "recipe_store", fresh)
    return fresh


@pytest.fixture
def image_path(tmp_path):
    p = tmp_path / "sample.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(str(p))
    return str(p)


class _FakeGui:
    def __init__(self):
        self.reloads: list[str] = []

    def reload_current_image_with_recipe(self, path: str) -> None:
        self.reloads.append(path)


class TestEditRecipeCommand:
    def test_redo_applies_new_recipe(self, store, image_path):
        gui = _FakeGui()
        cmd = recipe_commands.EditRecipeCommand(
            gui, image_path, Recipe(), Recipe(brightness=0.5),
        )
        cmd.redo()
        assert store.get_for_path(image_path).brightness == pytest.approx(0.5)

    def test_undo_restores_old_recipe(self, store, image_path):
        gui = _FakeGui()
        cmd = recipe_commands.EditRecipeCommand(
            gui, image_path,
            Recipe(brightness=0.1), Recipe(brightness=0.9),
        )
        cmd.redo()
        cmd.undo()
        assert store.get_for_path(image_path).brightness == pytest.approx(0.1)

    def test_redo_triggers_view_reload(self, store, image_path):
        gui = _FakeGui()
        cmd = recipe_commands.EditRecipeCommand(
            gui, image_path, Recipe(), Recipe(brightness=0.2),
        )
        cmd.redo()
        assert gui.reloads == [image_path]

    def test_reload_is_optional(self, store, image_path):
        class _Bare:
            pass
        cmd = recipe_commands.EditRecipeCommand(
            _Bare(), image_path, Recipe(), Recipe(brightness=0.3),
        )
        # Should not raise even without the reload hook.
        cmd.redo()

    def test_text_defaults_to_edit_recipe(self, store, image_path):
        cmd = recipe_commands.EditRecipeCommand(
            _FakeGui(), image_path, Recipe(), Recipe(),
        )
        assert cmd.text() == "Edit recipe"

    def test_custom_text_is_preserved(self, store, image_path):
        cmd = recipe_commands.EditRecipeCommand(
            _FakeGui(), image_path, Recipe(), Recipe(), text="Brighten",
        )
        assert cmd.text() == "Brighten"

    def test_state_snapshot_is_deep_copy(self, store, image_path):
        """Mutating the caller's recipe after construction must not affect the command."""
        gui = _FakeGui()
        new = Recipe(brightness=0.5)
        cmd = recipe_commands.EditRecipeCommand(
            gui, image_path, Recipe(brightness=0.1), new,
        )
        new.brightness = 0.99  # mutate the caller's copy
        cmd.redo()
        # The stored recipe must reflect the snapshot, not the later mutation.
        assert store.get_for_path(image_path).brightness == pytest.approx(0.5)
