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

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

from Imervue.image.recipe import Recipe, file_identity

logger = logging.getLogger("Imervue.recipe_store")

_STORE_FILENAME = "recipes.json"


def _default_store_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "recipes" / _STORE_FILENAME
    return Path.home() / ".config" / "imervue" / "recipes" / _STORE_FILENAME


class RecipeStore:
    """In-memory recipe index backed by a single JSON file.

    The public API is path-oriented (``get_for_path``, ``set_for_path``) —
    callers never deal with file identities directly. Internally we compute
    the identity on each call, which is cheap thanks to the mtime/size cache
    in ``recipe.file_identity``.
    """

    def __init__(self, store_path: Path | None = None):
        self._path = Path(store_path) if store_path is not None else _default_store_path()
        self._lock = threading.RLock()
        # identity -> {"recipe": {...}, "last_path": str}
        # "last_path" is informational — helps humans poke at the file.
        self._entries: dict[str, dict[str, Any]] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load_locked()

    def _load_locked(self) -> None:
        self._entries = {}
        try:
            if not self._path.exists():
                self._loaded = True
                return
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Recipe store read failed ({self._path}): {exc}")
            self._loaded = True
            return

        if not isinstance(data, dict):
            logger.warning(f"Recipe store at {self._path} is not a dict; ignoring")
            self._loaded = True
            return

        for identity, entry in data.items():
            if not isinstance(entry, dict):
                continue
            recipe_data = entry.get("recipe")
            if not isinstance(recipe_data, dict):
                continue
            # Validate by round-tripping through Recipe — drops entries that
            # can't be reconstructed (e.g. field type changes across versions)
            # instead of exploding on lookup later.
            try:
                Recipe.from_dict(recipe_data)
            except Exception:
                logger.debug(f"Dropping unreadable recipe entry for {identity}")
                continue
            variants_raw = entry.get("variants")
            variants: dict[str, dict[str, Any]] = {}
            if isinstance(variants_raw, dict):
                for name, v in variants_raw.items():
                    if not isinstance(v, dict):
                        continue
                    try:
                        Recipe.from_dict(v)
                    except Exception:
                        continue
                    variants[str(name)] = v
            self._entries[identity] = {
                "recipe": recipe_data,
                "last_path": entry.get("last_path", ""),
                "variants": variants,
            }
        self._loaded = True

    def _save_locked(self) -> None:
        """Atomic write via tmp + os.replace. Caller must hold the lock."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(f"Cannot create recipe store dir {self._path.parent}: {exc}")
            return
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    self._entries,
                    f,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            os.replace(tmp, self._path)
        except OSError as exc:
            logger.warning(f"Recipe store write failed ({self._path}): {exc}")
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

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
            except Exception:
                logger.debug(f"Recipe store entry for {identity} failed to decode")
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
    # Virtual copies — named recipe variants stored alongside the master.
    # ------------------------------------------------------------------

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
            except Exception:
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
        return self.list_variants(file_identity(path))

    def get_variant_for_path(self, path: str, name: str) -> Recipe | None:
        return self.get_variant(file_identity(path), name)

    def save_variant_for_path(
        self, path: str, name: str, recipe: Recipe,
    ) -> None:
        identity = file_identity(path)
        if identity:
            self.save_variant(identity, name, recipe, last_path=str(path))

    def delete_variant_for_path(self, path: str, name: str) -> None:
        self.delete_variant(file_identity(path), name)

    def rename_variant_for_path(
        self, path: str, old_name: str, new_name: str,
    ) -> bool:
        return self.rename_variant(file_identity(path), old_name, new_name)

    # ------------------------------------------------------------------
    # Public API — path-based convenience wrappers
    # ------------------------------------------------------------------

    def get_for_path(self, path: str) -> Recipe | None:
        identity = file_identity(path)
        return self.get(identity)

    def set_for_path(self, path: str, recipe: Recipe) -> None:
        identity = file_identity(path)
        if not identity:
            return
        self.set(identity, recipe, last_path=str(path))

    def delete_for_path(self, path: str) -> None:
        identity = file_identity(path)
        if identity:
            self.delete(identity)

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def _reset_for_tests(self) -> None:
        """Discard cached state so the next call re-reads from disk."""
        with self._lock:
            self._entries = {}
            self._loaded = False

    def __len__(self) -> int:
        self._ensure_loaded()
        with self._lock:
            return len(self._entries)


# Module-level singleton. Tests that need an isolated store should instantiate
# RecipeStore directly with a tmp path instead of poking at this global.
recipe_store = RecipeStore()
