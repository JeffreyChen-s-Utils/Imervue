"""Persisted "recently opened" file list.

A small ordered list of absolute paths the user has recently opened
(PSDs, stand-alone images, exported comic projects). The list lives
in ``user_setting_dict["paint_recent_files"]`` so it round-trips
through the same settings file the rest of the workspace uses.

Semantics:

* ``add(path)`` pushes the path to the front. Existing entries with
  the same path are removed first so the new entry deduplicates.
* The list is capped at :data:`RECENT_FILES_MAX`. Older entries fall
  off the back when the cap is exceeded.
* Empty / non-string paths are silently ignored — the file menu
  never shows blanks.

The class is thin and stateless beyond its dict key; it's safe to
instantiate ad-hoc inside menu builders rather than holding a
reference on the workspace.
"""
from __future__ import annotations

from collections.abc import Iterable

from Imervue.user_settings.user_setting_dict import user_setting_dict

RECENT_FILES_KEY = "paint_recent_files"
RECENT_FILES_MAX = 10


def add(path: str) -> None:
    """Push ``path`` to the front of the recent-files list."""
    if not path or not isinstance(path, str):
        return
    paths = _load()
    paths = [p for p in paths if p != path]
    paths.insert(0, path)
    if len(paths) > RECENT_FILES_MAX:
        paths = paths[:RECENT_FILES_MAX]
    user_setting_dict[RECENT_FILES_KEY] = paths


def paths() -> list[str]:
    """Return a copy of the current recent-files list."""
    return list(_load())


def clear() -> None:
    """Drop every recent-file entry."""
    user_setting_dict.pop(RECENT_FILES_KEY, None)


def remove(path: str) -> None:
    """Drop ``path`` from the list if present."""
    paths_now = _load()
    if path in paths_now:
        paths_now.remove(path)
        if paths_now:
            user_setting_dict[RECENT_FILES_KEY] = paths_now
        else:
            user_setting_dict.pop(RECENT_FILES_KEY, None)


def _load() -> list[str]:
    raw = user_setting_dict.get(RECENT_FILES_KEY) or []
    if not isinstance(raw, Iterable):
        return []
    out: list[str] = []
    for entry in raw:
        if isinstance(entry, str) and entry:
            out.append(entry)
    return out
