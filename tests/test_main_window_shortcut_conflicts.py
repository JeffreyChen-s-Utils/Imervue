"""No key is claimed twice on any main-window tab.

Two enabled shortcuts on one key in the same window are ambiguous to Qt, which
then fires neither: on the Paint tab the toolbar and the Tools menu both bound
every tool key, the main window's folder-tab ``Ctrl+T`` / ``Ctrl+W`` /
``Ctrl+Tab`` sat on top of Paint's Transform / Close Tab / tab cycling, and
New Comic Project shared ``Ctrl+Shift+N`` with Add Layer — 22 dead keys.

A tab's live shortcuts are the ones anywhere in the window (the main window's
own ``QShortcut``\\ s and its menu bar) plus the ones inside that tab's page.
"""
from __future__ import annotations

import collections

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QShortcut

from _qt_skip import pytestmark  # noqa: E402,F401


def _keys(obj) -> list[str]:
    if isinstance(obj, QAction):
        if not obj.isEnabled() or obj.shortcutContext() == Qt.ShortcutContext.WidgetShortcut:
            return []
        return [seq.toString() for seq in obj.shortcuts() if seq.toString()]
    if not obj.isEnabled() or obj.context() == Qt.ShortcutContext.WidgetShortcut:
        return []
    return [obj.key().toString()] if obj.key().toString() else []


def _label(obj) -> str:
    if isinstance(obj, QAction):
        return f"{type(obj.parent()).__name__}:{obj.text().replace('&', '')}"
    return f"QShortcut on {type(obj.parent()).__name__}"


def _conflicts(window, page) -> dict[str, list[str]]:
    owners = [s for s in window.findChildren(QShortcut) if s.parent() is window]
    owners += window.menuBar().findChildren(QAction)
    owners += page.findChildren(QAction) + page.findChildren(QShortcut)
    by_key: dict[str, list[str]] = collections.defaultdict(list)
    for obj in owners:
        for key in _keys(obj):
            by_key[key].append(_label(obj))
    return {key: labels for key, labels in by_key.items() if len(labels) > 1}


@pytest.fixture
def window(qapp):
    from Imervue.Imervue_main_window import ImervueMainWindow
    win = ImervueMainWindow()
    yield win
    win._release_for_close()  # noqa: SLF001 - stops the watchdog and tree workers
    ImervueMainWindow._live_windows.discard(win)  # noqa: SLF001
    win.deleteLater()


def test_no_tab_has_two_shortcuts_on_one_key(window):
    tabs = window._main_tabs  # noqa: SLF001
    found = {}
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index)
        conflicts = _conflicts(window, tabs.widget(index))
        if conflicts:
            found[tabs.tabText(index)] = conflicts
    assert found == {}


def test_folder_tab_keys_only_live_on_the_browse_tab(window):
    tabs = window._main_tabs  # noqa: SLF001
    folder_keys = {s.key().toString() for s in window._folder_tab_shortcuts}  # noqa: SLF001
    assert folder_keys == {"Ctrl+T", "Ctrl+W", "Ctrl+Tab", "Ctrl+Shift+Tab"}
    paint = tabs.indexOf(window._paint_page)  # noqa: SLF001
    tabs.setCurrentIndex(paint)
    assert [s.isEnabled() for s in window._folder_tab_shortcuts] == [False] * 4  # noqa: SLF001
    tabs.setCurrentIndex(0)
    assert [s.isEnabled() for s in window._folder_tab_shortcuts] == [True] * 4  # noqa: SLF001


def test_paint_keys_that_used_to_be_dead_have_one_owner(window):
    tabs = window._main_tabs  # noqa: SLF001
    tabs.setCurrentIndex(tabs.indexOf(window._paint_page))  # noqa: SLF001
    live: dict[str, list[str]] = collections.defaultdict(list)
    owners = [s for s in window.findChildren(QShortcut) if s.parent() is window]
    owners += window.paint_workspace.findChildren(QAction)
    owners += window.paint_workspace.findChildren(QShortcut)
    for obj in owners:
        for key in _keys(obj):
            live[key].append(_label(obj))
    for key in ("B", "G", "U", "M", "Ctrl+T", "Ctrl+W", "Ctrl+Tab", "Ctrl+Shift+N", "Ctrl+Alt+N", "Q"):
        assert len(live[key]) == 1, (key, live[key])
