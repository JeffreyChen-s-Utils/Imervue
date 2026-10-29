"""Central recipe store.

All recipes live in a single JSONL file under ``%LOCALAPPDATA%/Imervue/recipes/``
keyed by ``file_identity`` (see ``recipe.py``). One file for the entire library
is simpler than per-image sidecars, easier to back up, and survives renames
of the source image as long as the pixels are unchanged.

Concurrency model
-----------------
Writes take an in-process lock and atomically replace the on-disk file via
``os.replace`` after writing to a ``.tmp`` sibling. Multiple Imervue instances
sharing the same store are not supported — the last writer wins. That's
acceptable for a viewer running on a single user's machine.

Disk format
-----------
The file is JSON (not JSONL) — a single object mapping identity → recipe dict.
JSON was chosen over JSONL because the whole thing fits comfortably in memory
for any realistic library size (100k entries × ~200 bytes = 20 MB) and a
single ``json.load`` is faster than iterating lines for that size class.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from Imervue.image.recipe import Recipe, file_identity
from Imervue.image.recipe_store_identity import RecipeStoreIdentityMixin
from Imervue.image.recipe_store_persistence import (
    _RECIPE_DECODE_ERRORS,
    RecipeStorePersistenceMixin,
)
from Imervue.image.recipe_store_variants import RecipeStoreVariantsMixin
from Imervue.system.unreadable_guard import UnreadableFileGuard

logger = logging.getLogger("Imervue.recipe_store")

_STORE_FILENAME = "recipes.json"


def _default_store_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "recipes" / _STORE_FILENAME
    return Path.home() / ".config" / "imervue" / "recipes" / _STORE_FILENAME


class RecipeStore(
    RecipeStorePersistenceMixin,
    RecipeStoreVariantsMixin,
    RecipeStoreIdentityMixin,
):
    """In-memory recipe index backed by a single JSON file.

    The public API is path-oriented (``get_for_path``, ``set_for_path``) —
    callers never deal with file identities directly. Internally we compute
    the identity on each call, which is cheap thanks to the mtime/size cache
    in ``recipe.file_identity``. Loading and saving, virtual copies and
    re-keying live in the mixins of ``recipe_store_persistence``,
    ``recipe_store_variants`` and ``recipe_store_identity``.
    """

    def __init__(self, store_path: Path | None = None):
        self._path = Path(store_path) if store_path is not None else _default_store_path()
        self._lock = threading.RLock()
        # identity -> {"recipe": {...}, "last_path": str}
        # "last_path" is informational — helps humans poke at the file.
        self._entries: dict[str, dict[str, Any]] = {}
        # Entries this version can't decode, written back untouched: dropping
        # them on the next save lost them for good, even for a newer Imervue.
        self._undecodable: dict[str, Any] = {}
        # A store file that could not be read is copied aside before a save
        # replaces it (and every photo's edits in it) with what this session has.
        self._guard = UnreadableFileGuard(logger)
        self._loaded = False

    @property
    def path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------
    # Public API — identity-based
    # ------------------------------------------------------------------

    def get(self, identity: str) -> Recipe | None:
        if not identity:
            return None
        self._ensure_loaded()
        with self._lock:
            entry = self._entries.get(identity)
            if entry is None:
                return None
            try:
                return Recipe.from_dict(entry["recipe"])
            except _RECIPE_DECODE_ERRORS:
                logger.debug("Recipe store entry for %s failed to decode", identity,
                             exc_info=True)
                return None

    def set(self, identity: str, recipe: Recipe, last_path: str = "") -> None:
        if not identity:
            return
        self._ensure_loaded()
        with self._lock:
            if recipe.is_identity():
                # No-op recipe — drop only the active recipe, but keep any
                # saved variants so the user can still swap back to them.
                existing = self._entries.get(identity)
                variants = (existing or {}).get("variants") or {}
                if not variants:
                    if identity in self._entries:
                        del self._entries[identity]
                        self._save_locked()
                    return
                self._entries[identity] = {
                    "recipe": Recipe().to_dict(),
                    "last_path": last_path,
                    "variants": variants,
                }
                self._save_locked()
                return
            existing = self._entries.get(identity) or {}
            self._entries[identity] = {
                "recipe": recipe.normalized().to_dict(),
                "last_path": last_path,
                "variants": existing.get("variants") or {},
            }
            self._save_locked()

    def delete(self, identity: str) -> None:
        if not identity:
            return
        self._ensure_loaded()
        with self._lock:
            if identity in self._entries:
                del self._entries[identity]
                self._save_locked()

    # ------------------------------------------------------------------
    # Public API — path-based convenience wrappers
    # ------------------------------------------------------------------

    def get_for_path(self, path: str) -> Recipe | None:
        return self.get(self.identity_for(path))

    def set_for_path(self, path: str, recipe: Recipe) -> None:
        identity = self.identity_for(path)
        if not identity:
            return
        self.set(identity, recipe, last_path=str(path))

    def delete_for_path(self, path: str) -> None:
        identity = self.identity_for(path)
        if identity:
            self.delete(identity)

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def _reset_for_tests(self) -> None:
        """Discard cached state so the next call re-reads from disk."""
        with self._lock:
            self._entries = {}
            self._undecodable = {}
            self._guard = UnreadableFileGuard(logger)
            self._loaded = False

    def __len__(self) -> int:
        self._ensure_loaded()
        with self._lock:
            return len(self._entries)


# Module-level singleton. Tests that need an isolated store should instantiate
# RecipeStore directly with a tmp path instead of poking at this global.
recipe_store = RecipeStore()


def carry_recipe(path: str | Path, change: Callable[[], bool],
                 transform: Callable[[Recipe], Recipe | None] | None = None) -> bool:
    """Run *change*, which rewrites *path* in place, and keep *path*'s recipe with the file.

    The identity is the file's first bytes, where EXIF lives, so a metadata
    rewrite or a lossless quarter turn used to orphan the photo's Modify
    edits and virtual copies. After a *change* that returns True the recipe
    is re-keyed to the file's new identity (see :meth:`RecipeStore.rekey`).
    Returns what *change* returned; its exceptions propagate untouched.
    """
    old = recipe_store.identity_for(path)   # a pre-2 entry moves first, or it would be left behind
    done = change()
    if done and old:
        recipe_store.rekey(old, file_identity(path), transform)
    return done
