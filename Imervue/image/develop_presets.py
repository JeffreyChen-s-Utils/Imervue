"""Named develop presets and batch recipe sync.

A develop preset is a :class:`~Imervue.image.recipe.Recipe` saved under a
user-chosen name; applying one writes that recipe to one or more images through
the recipe store. The CRUD layer is Qt-free — it mutates the user-settings dict
and round-trips through ``Recipe.to_dict`` / ``Recipe.from_dict`` — so it is
unit-testable without any UI.
"""
from __future__ import annotations

from collections.abc import Iterable

from Imervue.image.recipe import Recipe

PRESETS_KEY = "develop_presets"


class DevelopPresetStore:
    """CRUD over the named-preset table stored in a settings dict.

    The dict is mutated in place (the app passes the live ``user_setting_dict``;
    tests pass a throwaway dict), so callers persist by their usual settings
    save path. A corrupt / missing table is replaced with an empty one rather
    than raising, so a hand-edited settings file can't break the dialog.
    """

    def __init__(self, settings: dict) -> None:
        self._settings = settings

    def _table(self) -> dict:
        table = self._settings.get(PRESETS_KEY)
        if not isinstance(table, dict):
            table = {}
            self._settings[PRESETS_KEY] = table
        return table

    def names(self) -> list[str]:
        """Preset names, sorted for a stable list order."""
        return sorted(self._table())

    def save(self, name: str, recipe: Recipe) -> bool:
        """Store *recipe* under *name* (overwriting). Empty names are rejected."""
        name = (name or "").strip()
        if not name:
            return False
        self._table()[name] = recipe.to_dict()
        return True

    def get(self, name: str) -> Recipe | None:
        """Return the preset's recipe, or None if absent / unreadable."""
        data = self._table().get(name)
        if not isinstance(data, dict):
            return None
        try:
            return Recipe.from_dict(data)
        except (TypeError, ValueError, KeyError):
            return None

    def delete(self, name: str) -> bool:
        """Remove *name*; returns True if it existed."""
        return self._table().pop(name, None) is not None

    def rename(self, old: str, new: str) -> bool:
        """Rename *old* to *new*. Rejects empty / duplicate / missing names."""
        new = (new or "").strip()
        table = self._table()
        if not new or old == new or old not in table or new in table:
            return False
        table[new] = table.pop(old)
        return True


def apply_recipe_to_paths(recipe: Recipe, paths: Iterable[str], store) -> int:
    """Write *recipe* to every path through *store*; returns the count applied.

    Each path gets an independent clone (a ``to_dict`` round-trip) so a later
    per-image edit can never bleed across the images that shared the preset.
    """
    payload = recipe.to_dict()
    count = 0
    for path in paths:
        store.set_for_path(str(path), Recipe.from_dict(payload))
        count += 1
    return count
