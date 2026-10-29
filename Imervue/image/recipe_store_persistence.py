"""Reading and writing the recipe store's JSON file.

The lazy first load, the per-entry and per-variant decode filtering (entries
this version can't decode are kept aside and written back untouched), and
the atomic tmp + ``os.replace`` save. ``RecipeStore`` mixes this in; the
state it works on (``_path``, ``_lock``, ``_entries``, ``_undecodable``,
``_guard``, ``_loaded``) is set up by ``RecipeStore.__init__``.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from Imervue.image.recipe import Recipe

logger = logging.getLogger("Imervue.recipe_store")

# What ``Recipe.from_dict`` raises on malformed stored data: wrong types
# (``int(None)``, a non-mapping ``extra``), unparsable numbers, short curve points.
_RECIPE_DECODE_ERRORS = (TypeError, ValueError, IndexError)


class RecipeStorePersistenceMixin:
    """Load the store file once and save it atomically; mixed into ``RecipeStore``."""

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load_locked()

    def _read_store_file(self) -> dict | None:
        """Return the parsed on-disk store, or None on any read / format error."""
        try:
            if not self._path.exists():
                return None
            with open(self._path, encoding="utf-8-sig") as f:   # a BOM from a text editor is fine
                data = json.load(f)
        except (OSError, ValueError, RecursionError) as exc:   # ValueError: bad JSON or UTF-8
            logger.warning(f"Recipe store read failed ({self._path}): {exc}")
            self._guard.note_unreadable(self._path)
            return None
        if not isinstance(data, dict):
            logger.warning(f"Recipe store at {self._path} is not a dict; ignoring")
            self._guard.note_unreadable(self._path)
            return None
        return data

    @staticmethod
    def _parse_variants(variants_raw: Any) -> dict[str, dict[str, Any]]:
        variants: dict[str, dict[str, Any]] = {}
        if not isinstance(variants_raw, dict):
            return variants
        for name, v in variants_raw.items():
            if not isinstance(v, dict):
                continue
            try:
                Recipe.from_dict(v)
            except Exception as exc:  # noqa: BLE001 - tolerate any decode error
                logger.debug(f"Dropping unreadable variant '{name}': {exc}")
                continue
            variants[str(name)] = v
        return variants

    @classmethod
    def _parse_entry(cls, entry: Any) -> dict[str, Any] | None:
        if not isinstance(entry, dict):
            return None
        recipe_data = entry.get("recipe")
        if not isinstance(recipe_data, dict):
            return None
        try:
            Recipe.from_dict(recipe_data)
        except _RECIPE_DECODE_ERRORS:
            logger.debug("Dropping undecodable recipe store entry", exc_info=True)
            return None
        return {
            "recipe": recipe_data,
            "last_path": entry.get("last_path", ""),
            "variants": cls._parse_variants(entry.get("variants")),
        }

    def _load_locked(self) -> None:
        self._entries = {}
        self._undecodable = {}
        data = self._read_store_file()
        if data is None:
            self._loaded = True
            return
        for identity, entry in data.items():
            parsed = self._parse_entry(entry)
            if parsed is None:
                logger.debug(f"Keeping undecodable recipe entry for {identity} as it is")
                self._undecodable[identity] = entry
                continue
            self._entries[identity] = parsed
        self._loaded = True

    def _save_locked(self) -> None:
        """Atomic write via tmp + os.replace. Caller must hold the lock.

        Undecodable entries go back as they were read; a store file that
        could not be read is only replaced once a copy of it is kept.
        """
        if not self._guard.clear_to_save(self._path):
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(f"Cannot create recipe store dir {self._path.parent}: {exc}")
            return
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {**self._undecodable, **self._entries},
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
