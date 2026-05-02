"""Reference Pins — pinned reference-image basket for visual comparison.

The pinned set persists across restarts in
``user_setting_dict["reference_pins"]`` so you can keep a colour
palette / mood-board / "this is the look I'm matching" reference open
beside the editing pane between sessions.

The list is treated as an ordered, de-duplicated set of absolute paths.
The Qt-side panel lives in :mod:`Imervue.gui.reference_panel_dialog`;
this module is intentionally Qt-free so it can be unit-tested without a
display server.
"""
from __future__ import annotations

from collections.abc import Iterable

from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict

_KEY = "reference_pins"


def _pins() -> list[str]:
    lst = user_setting_dict.get(_KEY)
    if not isinstance(lst, list):
        lst = []
        user_setting_dict[_KEY] = lst
    return lst


def get_all() -> list[str]:
    """Return a copy of the current pinned references."""
    return list(_pins())


def count() -> int:
    return len(_pins())


def contains(path: str) -> bool:
    return bool(path) and path in _pins()


def add(path: str) -> bool:
    """Add ``path`` to the pin list. Returns ``True`` if it was new."""
    if not path:
        return False
    pins = _pins()
    if path in pins:
        return False
    pins.append(path)
    schedule_save()
    return True


def add_many(paths: Iterable[str]) -> int:
    """Add every entry in ``paths``; returns the number of new entries."""
    pins = _pins()
    added = 0
    for p in paths:
        if p and p not in pins:
            pins.append(p)
            added += 1
    if added:
        schedule_save()
    return added


def remove(path: str) -> bool:
    pins = _pins()
    if path not in pins:
        return False
    pins.remove(path)
    schedule_save()
    return True


def clear() -> None:
    pins = _pins()
    if pins:
        pins.clear()
        schedule_save()


def move(path: str, *, up: bool) -> bool:
    """Reorder a single entry one step up or down. Returns ``True`` on change."""
    pins = _pins()
    if path not in pins:
        return False
    idx = pins.index(path)
    target = idx - 1 if up else idx + 1
    if target < 0 or target >= len(pins):
        return False
    pins[idx], pins[target] = pins[target], pins[idx]
    schedule_save()
    return True
