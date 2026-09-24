"""Saved per-image data follows a file to its new path.

Ratings, favourites, tags, colour labels, titles, descriptions, bookmarks,
albums, the staging tray, reference pins and the recent-images list are
stored in user settings keyed by the image's path. When Imervue renames or
moves a file, :func:`move_path_metadata` re-keys all of it, so the photo keeps
its stars and tags instead of leaving them under a path that no longer exists.
"""
from __future__ import annotations

import os
from collections.abc import Iterable, Mapping

# {path: value}
_VALUE_KEYS = ("image_ratings", "image_color_labels", "image_titles", "image_descriptions")
# [path, ...]
_LIST_KEYS = ("image_favorites", "bookmarks", "staging_tray", "reference_pins",
              "user_recent_images")
# {name: [path, ...]}
_GROUP_KEYS = ("image_tags", "albums")


def _move_values(store: dict, mapping: Mapping[str, str], *, keep_existing: bool) -> bool:
    """Re-key *store* ``{path: value}`` at once: ``a→b`` beside ``b→c`` moves each value once."""
    if keep_existing:
        moving = {old: store[old] for old, new in mapping.items()
                  if old in store and new not in store}
    else:
        moving = {old: store[old] for old in mapping if old in store}
    stale = [] if keep_existing else [
        new for new in mapping.values() if new in store and new not in mapping]
    for old in moving:
        del store[old]
    for new in stale:                     # left by a file that used to live there
        del store[new]
    for old, value in moving.items():
        store[mapping[old]] = value
    return bool(moving or stale)


def _moved_list(paths: list, mapping: Mapping[str, str], *, keep_existing: bool) -> list | None:
    """*paths* with old paths replaced by new ones, order kept, no duplicates; None if unchanged."""
    present = set(paths)
    stale = set() if keep_existing else {
        new for old, new in mapping.items()
        if new in present and old not in present and new not in mapping}
    out: list = []
    seen: set = set()
    for path in paths:
        if path in stale:
            continue
        new = mapping.get(path, path) if isinstance(path, str) else path
        if keep_existing and new != path and new in present:
            new = path
        if new not in seen:
            seen.add(new)
            out.append(new)
    return None if out == paths else out


def stored_paths() -> set[str]:
    """Every image path any of these settings keeps."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    found: set[str] = set()
    for key in _VALUE_KEYS:
        store = user_setting_dict.get(key)
        if isinstance(store, dict):
            found.update(path for path in store if isinstance(path, str))
    lists = [user_setting_dict.get(key) for key in _LIST_KEYS]
    for key in _GROUP_KEYS:
        groups = user_setting_dict.get(key)
        if isinstance(groups, dict):
            lists.extend(groups.values())
    for paths in lists:
        if isinstance(paths, list):
            found.update(path for path in paths if isinstance(path, str))
    return found


def folder_moves(old_folder: str, new_folder: str, paths: Iterable[str]) -> dict[str, str]:
    """``{old: new}`` for each of *paths* inside *old_folder*, now under *new_folder*.

    Matching follows the file system's case rules (``C:\\Shoot`` holds
    ``c:\\shoot\\a.jpg`` on Windows); the part below the folder keeps its
    spelling.
    """
    prefix = os.path.normcase(os.path.join(os.path.abspath(old_folder), ""))
    target = os.path.join(os.path.abspath(new_folder), "")
    moves: dict[str, str] = {}
    for path in paths:
        absolute = os.path.abspath(path)
        if os.path.normcase(absolute).startswith(prefix):
            moves[path] = target + absolute[len(prefix):]
    return moves


def move_path_metadata(mapping: Mapping[str, str], *, keep_existing: bool = False) -> bool:
    """Re-key every saved per-image value from each old path in *mapping* to its new path.

    Called after Imervue renamed or moved the files, so nothing else can have
    been saved for a new path yet: a value found under one belonged to a file
    that used to live there and is dropped. With *keep_existing* (relinking
    files that went missing, whose new path may already carry data of its
    own) a new path's value wins and the old one is left alone. Returns
    whether anything changed; the settings file is saved if so. Lists and
    tag / album members are replaced with new list objects, which also
    refreshes the bookmark lookup cache.
    """
    from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict
    pairs = {old: new for old, new in mapping.items() if old != new}
    if not pairs:
        return False
    changed = False
    for key in _VALUE_KEYS:
        store = user_setting_dict.get(key)
        if isinstance(store, dict):
            changed |= _move_values(store, pairs, keep_existing=keep_existing)
    for key in _LIST_KEYS:
        paths = user_setting_dict.get(key)
        if isinstance(paths, list):
            moved = _moved_list(paths, pairs, keep_existing=keep_existing)
            if moved is not None:
                user_setting_dict[key] = moved
                changed = True
    for key in _GROUP_KEYS:
        groups = user_setting_dict.get(key)
        if not isinstance(groups, dict):
            continue
        for name, paths in groups.items():
            if isinstance(paths, list):
                moved = _moved_list(paths, pairs, keep_existing=keep_existing)
                if moved is not None:
                    groups[name] = moved
                    changed = True
    if changed:
        schedule_save()
    return changed
