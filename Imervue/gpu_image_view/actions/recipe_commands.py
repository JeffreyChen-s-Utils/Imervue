"""QUndoCommand wrappers for non-destructive recipe edits.

The Develop panel pushes one of these onto the view's undo stack every time
the user nudges a slider or hits rotate. Each command stores the old/new
recipe as plain dicts so undo/redo is trivial — just re-apply whichever
state the user wants and ask the view to reload the current image.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class EditRecipeCommand(QUndoCommand):
    """Reversible 'update the recipe for this file' action.

    We intentionally do *not* merge consecutive commands (``mergeWith``) even
    though slider drags produce many — the develop panel debounces at the
    input level, so by the time a command reaches here it represents a
    committed edit the user will want to step through individually.
    """

    def __init__(
        self,
        main_gui: "GPUImageView",
        path: str,
        old_recipe: Recipe,
        new_recipe: Recipe,
        text: str = "Edit recipe",
    ):
        super().__init__(text)
        self._main_gui = main_gui
        self._path = path
        # Deep copy via dict round-trip so later in-place mutation of the
        # caller's recipe can't corrupt the undo state.
        self._old: dict[str, Any] = old_recipe.to_dict()
        self._new: dict[str, Any] = new_recipe.to_dict()

    def _apply(self, recipe_dict: dict[str, Any]) -> None:
        recipe = Recipe.from_dict(recipe_dict)
        recipe_store.set_for_path(self._path, recipe)
        # Notify the view to reload with the new recipe. Keep the call
        # optional so tests that don't need a full GUI can still exercise
        # the command's state logic.
        reload = getattr(self._main_gui, "reload_current_image_with_recipe", None)
        if callable(reload):
            reload(self._path)

    def redo(self) -> None:
        self._apply(self._new)

    def undo(self) -> None:
        self._apply(self._old)
