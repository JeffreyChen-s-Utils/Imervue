"""Sort, filter and group image paths before a web-gallery export.

``web_gallery.generate_web_gallery`` takes a raw path list; these pure helpers
organise that list first — order by name / modified time / size, filter by a
filename glob, or group into sections by extension / parent folder / capture
date. Path + stat only, no Qt.
"""
from __future__ import annotations

import fnmatch
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path

_SORT_ORDERS = ("name", "mtime", "size")
_GROUP_KEYS = ("ext", "parent", "date")
_NO_EXT = "(no extension)"
_UNKNOWN_DATE = "unknown"


def _stat_attr(path: str, attr: str) -> float:
    try:
        return float(getattr(Path(path).stat(), attr))
    except OSError:
        return 0.0


def sort_images(
    paths: Iterable[str], order: str = "name", *, reverse: bool = False,
) -> list[str]:
    """Return *paths* sorted by ``name`` / ``mtime`` / ``size``.

    Unreadable files sort as if name-empty / zero-stat rather than raising.
    """
    keys: dict[str, Callable[[str], object]] = {
        "name": lambda p: Path(p).name.lower(),
        "mtime": lambda p: _stat_attr(p, "st_mtime"),
        "size": lambda p: _stat_attr(p, "st_size"),
    }
    key = keys.get(order)
    if key is None:
        raise ValueError(f"unknown sort order {order!r}; expected one of {_SORT_ORDERS}")
    return sorted(paths, key=key, reverse=reverse)


def filter_images(paths: Iterable[str], pattern: str) -> list[str]:
    """Keep paths whose filename matches the case-insensitive glob *pattern*.

    An empty pattern keeps everything.
    """
    if not pattern:
        return list(paths)
    needle = pattern.lower()
    return [p for p in paths if fnmatch.fnmatch(Path(p).name.lower(), needle)]


def _group_key(path: str, by: str) -> str:
    if by == "ext":
        return Path(path).suffix.lower().lstrip(".") or _NO_EXT
    if by == "parent":
        return Path(path).parent.name
    try:
        return datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return _UNKNOWN_DATE


def group_images(paths: Iterable[str], by: str = "ext") -> dict[str, list[str]]:
    """Group *paths* into ``{section: [paths]}`` by ``ext`` / ``parent`` / ``date``."""
    if by not in _GROUP_KEYS:
        raise ValueError(f"unknown group key {by!r}; expected one of {_GROUP_KEYS}")
    groups: dict[str, list[str]] = {}
    for path in paths:
        groups.setdefault(_group_key(path, by), []).append(path)
    return groups
