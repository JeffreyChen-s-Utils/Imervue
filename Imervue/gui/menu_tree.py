"""Walk menu trees without ``QAction.menu()``.

PySide6 (seen on 6.11.0 and 6.11.1) re-parents the ``QMenu`` wrapper that
``QAction.menu()`` returns under the temporary ``QAction`` wrapper in
shiboken's ownership tree. When that action wrapper is garbage-collected,
shiboken invalidates the menu wrapper, including every reference to it cached
elsewhere (``main_window.language_menu``, ``main_window._plugin_menu``, a
workspace's ``_file_menu``). The next call on such a reference raises
"Internal C++ object ... already deleted" although the menu is alive; that is
how the plugin languages vanished from the Language menu.

These helpers resolve a submenu through ``QMenu.menuAction()`` of the menus
found with ``findChildren`` instead, which leaves existing wrappers alone.
"""
from __future__ import annotations

from collections.abc import Iterator

import shiboken6
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


def _address(obj: QObject) -> int:
    return shiboken6.getCppPointer(obj)[0]


def submenu_index(owner: QObject) -> dict[int, QMenu]:
    """Map each ``QMenu`` under ``owner`` by the C++ address of its menu action.

    ``owner`` must be an ancestor of every menu the walk should see: the menu
    bar for menus built with ``addMenu(title)``, the window for menus created
    with the window as parent and added with ``addMenu(menu)``.
    """
    return {_address(menu.menuAction()): menu for menu in owner.findChildren(QMenu)}


def submenu_of(action: QAction, index: dict[int, QMenu]) -> QMenu | None:
    """Return the submenu ``action`` opens, or ``None`` for a plain action."""
    return index.get(_address(action))


def iter_menu_actions(
    container: QObject, index: dict[int, QMenu], path: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], QAction]]:
    """Yield ``(path, action)`` for every leaf action under ``container``, in menu order.

    ``path`` holds the titles of the enclosing menus (``&`` mnemonics
    stripped). Separators and submenu actions themselves are not yielded.
    """
    for action in container.actions():
        if action.isSeparator():
            continue
        sub = submenu_of(action, index)
        if sub is None:
            yield path, action
            continue
        yield from iter_menu_actions(sub, index, (*path, action.text().replace("&", "").strip()))
