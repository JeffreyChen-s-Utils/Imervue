"""Virtual copies: named recipe variants stored alongside an image's master recipe.

Identity-keyed list / get / save / delete / rename of variants and their
path-keyed wrappers. ``RecipeStore`` mixes this in and supplies the loaded
index, the lock, ``_ensure_loaded`` / ``_save_locked`` and ``identity_for``.
"""
from __future__ import annotations

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store_persistence import _RECIPE_DECODE_ERRORS, logger


class RecipeStoreVariantsMixin:
    """Named recipe variants of one image; mixed into ``RecipeStore``."""

    def list_variants(self, identity: str) -> list[str]:
        """Return the names of saved variants (excluding the active master)."""
        if not identity:
            return []
        self._ensure_loaded()
        with self._lock:
            entry = self._entries.get(identity)
            if not entry:
                return []
            return sorted((entry.get("variants") or {}).keys())

    def get_variant(self, identity: str, name: str) -> Recipe | None:
        if not identity or not name:
            return None
        self._ensure_loaded()
        with self._lock:
            entry = self._entries.get(identity)
            if not entry:
                return None
            variants = entry.get("variants") or {}
            data = variants.get(name)
            if not isinstance(data, dict):
                return None
            try:
                return Recipe.from_dict(data)
            except _RECIPE_DECODE_ERRORS:
                logger.debug("Variant %r of %s failed to decode", name, identity,
                             exc_info=True)
                return None

    def save_variant(
        self, identity: str, name: str, recipe: Recipe, last_path: str = "",
    ) -> None:
        name = name.strip()
        if not identity or not name:
            return
        self._ensure_loaded()
        with self._lock:
            entry = self._entries.get(identity) or {
                "recipe": Recipe().to_dict(),
                "last_path": last_path,
                "variants": {},
            }
            variants = dict(entry.get("variants") or {})
            variants[name] = recipe.normalized().to_dict()
            entry["variants"] = variants
            if last_path:
                entry["last_path"] = last_path
            self._entries[identity] = entry
            self._save_locked()

    def delete_variant(self, identity: str, name: str) -> None:
        if not identity or not name:
            return
        self._ensure_loaded()
        with self._lock:
            entry = self._entries.get(identity)
            if not entry:
                return
            variants = dict(entry.get("variants") or {})
            if name in variants:
                del variants[name]
                entry["variants"] = variants
                self._save_locked()

    def rename_variant(self, identity: str, old_name: str, new_name: str) -> bool:
        new_name = new_name.strip()
        if not identity or not old_name or not new_name or old_name == new_name:
            return False
        self._ensure_loaded()
        with self._lock:
            entry = self._entries.get(identity)
            if not entry:
                return False
            variants = dict(entry.get("variants") or {})
            if old_name not in variants or new_name in variants:
                return False
            variants[new_name] = variants.pop(old_name)
            entry["variants"] = variants
            self._save_locked()
            return True

    def list_variants_for_path(self, path: str) -> list[str]:
        return self.list_variants(self.identity_for(path))

    def get_variant_for_path(self, path: str, name: str) -> Recipe | None:
        return self.get_variant(self.identity_for(path), name)

    def save_variant_for_path(
        self, path: str, name: str, recipe: Recipe,
    ) -> None:
        identity = self.identity_for(path)
        if identity:
            self.save_variant(identity, name, recipe, last_path=str(path))

    def delete_variant_for_path(self, path: str, name: str) -> None:
        self.delete_variant(self.identity_for(path), name)

    def rename_variant_for_path(
        self, path: str, old_name: str, new_name: str,
    ) -> bool:
        return self.rename_variant(self.identity_for(path), old_name, new_name)
