"""Integrity checks and clean-up for tag / album collections.

``user_settings.tags`` is plain CRUD over ``{name: [path, ...]}`` dicts: it
never validates a name, lets ``"Foo"`` and ``"foo"`` coexist (rename only
blocks an exact-case clash), and leaves a path in a tag after the file is gone.
These pure helpers surface those problems and produce a cleaned copy so the UI
can warn before a rename / merge or prune stale state on load. Every function
takes the dict(s) as arguments and returns new structures — no settings I/O,
no mutation of the input.
"""
from __future__ import annotations

from collections.abc import Mapping

# Characters that break a tag/album name used as a dict key or shown in a menu.
_ILLEGAL_NAME_CHARS = ("\n", "\r", "\t")
Collection = Mapping[str, list[str]]


def _normalise(name: str) -> str:
    return name.strip().casefold()


def validate_tag_name(name: str) -> bool:
    """Return True when *name* is a usable tag/album name.

    Rejects non-strings, blank / whitespace-only names, names with leading or
    trailing whitespace (a silent source of duplicate keys), and names carrying
    a newline / tab.
    """
    if not isinstance(name, str) or not name.strip():
        return False
    if name != name.strip():
        return False
    return not any(char in name for char in _ILLEGAL_NAME_CHARS)


def find_duplicate_names(collection: Collection) -> dict[str, list[str]]:
    """Return ``{normalised_name: [original names]}`` for case- / whitespace-
    insensitive duplicates (only groups with more than one name)."""
    groups: dict[str, list[str]] = {}
    for name in collection:
        groups.setdefault(_normalise(name), []).append(name)
    return {key: sorted(names) for key, names in groups.items() if len(names) > 1}


def find_name_collisions(tags: Collection, albums: Collection) -> list[str]:
    """Return normalised names that exist as both a tag and an album."""
    tag_keys = {_normalise(name) for name in tags}
    album_keys = {_normalise(name) for name in albums}
    return sorted(tag_keys & album_keys)


def find_orphaned_paths(
    collection: Collection, existing_paths: set[str],
) -> dict[str, list[str]]:
    """Return ``{name: [paths]}`` for paths no longer in *existing_paths*
    (only collections that have at least one orphan)."""
    orphans: dict[str, list[str]] = {}
    for name, paths in collection.items():
        missing = [path for path in paths if path not in existing_paths]
        if missing:
            orphans[name] = missing
    return orphans


def find_empty_collections(collection: Collection) -> list[str]:
    """Return names whose path list is empty."""
    return [name for name, paths in collection.items() if not paths]


def prune_orphaned_paths(
    collection: Collection, existing_paths: set[str],
) -> dict[str, list[str]]:
    """Return a copy of *collection* with paths not in *existing_paths* removed.

    Empty collections are kept — a tag with no images is still a valid tag.
    """
    return {
        name: [path for path in paths if path in existing_paths]
        for name, paths in collection.items()
    }


def merge_collections(
    collection: Collection, source: str, target: str,
) -> dict[str, list[str]]:
    """Return a copy of *collection* with *source* folded into *target*.

    The merged list is the order-preserving, de-duplicated union of the target's
    paths followed by the source's; *source* is removed. A no-op (plain copy) if
    *source* is absent or equals *target*. When *target* is absent this acts as
    a rename of *source* to *target*.
    """
    result = {name: list(paths) for name, paths in collection.items()}
    if source not in result or source == target:
        return result
    source_paths = result.pop(source)
    combined = list(result.get(target, []))
    seen = set(combined)
    for path in source_paths:
        if path not in seen:
            seen.add(path)
            combined.append(path)
    result[target] = combined
    return result
