"""Bind the user's shortcut remaps (:mod:`shortcut_registry`) to the live actions.

Every action a registry entry describes is tagged once, where it is built, with
:func:`tag_registry_shortcut`. :func:`apply_registry_bindings` then rebinds each
tagged ``QAction`` / ``QShortcut`` under a widget. Only the key the registry owns
is replaced, so an extra alias (Redo's ``Ctrl+Y`` next to ``Ctrl+Shift+Z``)
survives a remap.
"""
from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QWidget

from Imervue.paint.shortcut_registry import default_key

# Dynamic property holding the registry key an object is bound to right now.
_BOUND_KEY = "paint_registry_key"


def tag_registry_shortcut(obj: QAction | QShortcut, action_id: str) -> bool:
    """Mark ``obj`` as the owner of registry entry ``action_id``.

    ``obj`` must already carry the entry's default key. Returns ``False`` and
    leaves ``obj`` alone when the registry has no such entry.
    """
    key = default_key(action_id)
    if key is None:
        return False
    obj.setObjectName(action_id)
    obj.setProperty(_BOUND_KEY, key)
    return True


def registry_shortcut(parent: QObject, action_id: str) -> QShortcut:
    """Return a new ``QShortcut`` on ``parent`` bound to ``action_id``'s default key."""
    key = default_key(action_id)
    if key is None:
        raise KeyError(action_id)
    shortcut = QShortcut(QKeySequence(key), parent)
    tag_registry_shortcut(shortcut, action_id)
    return shortcut


def apply_registry_bindings(root: QObject, bindings: Mapping[str, str]) -> int:
    """Rebind every tagged action under ``root`` to ``bindings``; return how many changed."""
    changed = 0
    for obj in [*root.findChildren(QAction), *root.findChildren(QShortcut)]:
        bound = obj.property(_BOUND_KEY)
        key = bindings.get(obj.objectName())
        if bound is None or not key or key == bound:
            continue
        _rebind(obj, bound, key)
        changed += 1
    return changed


def fixed_shortcut_keys(root: QWidget, other_label: str) -> dict[str, str]:
    """Return the keys that actions outside the registry hold, each mapped to a label.

    Covers everything under ``root`` plus what its window binds for every tab
    (the window's own ``QShortcut`` objects and its menu bar), so a remap that would
    make a key ambiguous can be flagged. Disabled and widget-scoped shortcuts
    are skipped; a ``QShortcut`` has no text, so it reports ``other_label``.
    """
    owners = [*root.findChildren(QAction), *root.findChildren(QShortcut)]
    window = root.window()
    if window is not root:
        owners += [s for s in window.findChildren(QShortcut) if s.parent() is window]
        if isinstance(window, QMainWindow):
            owners += window.menuBar().findChildren(QAction)
    taken: dict[str, str] = {}
    for obj in owners:
        if obj.property(_BOUND_KEY) is not None or not obj.isEnabled():
            continue
        for key in _live_keys(obj):
            taken.setdefault(key, _label(obj, other_label))
    return taken


def _live_keys(obj: QAction | QShortcut) -> list[str]:
    if isinstance(obj, QShortcut):
        if obj.context() == Qt.ShortcutContext.WidgetShortcut:
            return []
        keys = [obj.key()]
    else:
        if obj.shortcutContext() == Qt.ShortcutContext.WidgetShortcut:
            return []
        keys = obj.shortcuts()
    return [k.toString() for k in keys if k.toString()]


def _label(obj: QAction | QShortcut, other_label: str) -> str:
    text = obj.text().replace("&", "") if isinstance(obj, QAction) else ""
    return text or other_label


def _rebind(obj: QAction | QShortcut, old: str, new: str) -> None:
    sequence = QKeySequence(new)
    if isinstance(obj, QShortcut):
        obj.setKey(sequence)
    else:
        keys = obj.shortcuts()
        if any(k.toString() == old for k in keys):
            keys = [sequence if k.toString() == old else k for k in keys]
        else:
            keys = [sequence, *keys]
        obj.setShortcuts(keys)
    obj.setProperty(_BOUND_KEY, new)
