"""Keeping a stored recipe with a file whose identity changed.

``rekey`` moves a recipe and its variants to a new identity after Imervue
rewrote the file without touching its pixels (new EXIF, a quarter turn);
``identity_for`` moves an entry still under a file's pre-2 identity to the
current one on first lookup. ``RecipeStore`` mixes this in and supplies the
loaded index, the lock and ``_ensure_loaded`` / ``_save_locked``.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from Imervue.image.recipe import Recipe, file_identities
from Imervue.image.recipe_store_persistence import _RECIPE_DECODE_ERRORS, logger


class RecipeStoreIdentityMixin:
    """Re-keying of stored recipes when a file's identity changes; mixed into ``RecipeStore``."""

    def rekey(self, old_identity: str, new_identity: str,
              transform: Callable[[Recipe], Recipe | None] | None = None) -> bool:
        """Move *old_identity*'s recipe and variants to *new_identity*; True if they moved.

        For a file Imervue rewrote without touching its pixels — new EXIF,
        a quarter turn — whose identity (its first bytes) changed. With
        *transform* every recipe, the variants included, is passed through
        it first; if it returns ``None`` for any of them nothing moves, so
        the recipe stays where it was rather than half-adapted.
        """
        if not old_identity or not new_identity or old_identity == new_identity:
            return False
        self._ensure_loaded()
        with self._lock:
            entry = self._entries.get(old_identity)
            if entry is None:
                return False
            if transform is not None:
                entry = _transformed_entry(entry, transform)
                if entry is None:
                    return False
            self._entries[new_identity] = entry
            del self._entries[old_identity]
            self._save_locked()
            return True

    def identity_for(self, path: str | Path) -> str:
        """*path*'s identity, first moving a recipe stored under its pre-2 identity to it.

        Identities used to hash only the first 4 KB and the size, which two
        scanned pages of one size (BMP, uncompressed TIFF) shared: every page
        showed one recipe. An entry still under a file's old identity moves to
        the new one the first time the file is looked up, so nobody's edits
        disappear with the upgrade; a second file that shared it starts clean.
        """
        identity, legacy = file_identities(path)
        if not identity:
            return ""
        self._ensure_loaded()
        with self._lock:
            if identity not in self._entries and legacy in self._entries:
                self._entries[identity] = self._entries.pop(legacy)
                self._save_locked()
        return identity


def _transformed_entry(entry: dict[str, Any],
                       transform: Callable[[Recipe], Recipe | None]) -> dict[str, Any] | None:
    """*entry* with its recipe and each variant passed through *transform*; None if one can't be."""
    try:
        recipe = transform(Recipe.from_dict(entry["recipe"]))
        variants = {name: (transform(Recipe.from_dict(data)) if isinstance(data, dict) else data)
                    for name, data in (entry.get("variants") or {}).items()}
    except _RECIPE_DECODE_ERRORS:
        logger.debug("A recipe failed to decode while following its file", exc_info=True)
        return None
    if recipe is None or any(variant is None for variant in variants.values()):
        return None
    return {**entry, "recipe": recipe.normalized().to_dict(),
            "variants": {name: (variant.normalized().to_dict()
                                if isinstance(variant, Recipe) else variant)
                         for name, variant in variants.items()}}
