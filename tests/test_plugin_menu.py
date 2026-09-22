"""Plugins menu: entries added by plugins are tracked and removed on reload.

Reload used to run every plugin's menu hook again without taking the old
entries out, so each reload duplicated them and the old ones kept calling
unloaded plugin instances. It also used the cached ``_plugin_menu`` wrapper,
which the command palette's menu walk could invalidate.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QMenu, QMessageBox

from Imervue.menu import extra_tools_menu, plugin_menu


class _Plugin:
    """Adds one entry to the Plugins menu, a submenu, and one Extra Tools entry."""

    def __init__(self, window):
        self._window = window

    def on_build_menu_bar(self, menu):
        menu.addAction("Plain entry")
        sub = menu.addMenu("Plugin submenu")
        sub.addAction("Inside submenu")
        retouch = self._window.findChild(
            QMenu, extra_tools_menu.submenu_object_name("retouch_submenu"))
        retouch.addAction("Extra Tools entry")


class _SharingPlugin:
    """Joins the submenu another plugin created, found with findChildren (like safety_review)."""

    def __init__(self, window):
        del window

    def on_build_menu_bar(self, menu):
        shared = next(
            m for m in menu.findChildren(QMenu, options=Qt.FindChildOption.FindDirectChildrenOnly)
            if m.title() == "Plugin submenu"
        )
        shared.addAction("Shared entry")


class _Manager:
    def __init__(self, window):
        self.window = window
        self.plugins: list = []
        self.unloaded = 0

    def discover_and_load(self):
        self.plugins = [_Plugin(self.window), _SharingPlugin(self.window)]

    def unload_all(self):
        self.unloaded += 1
        self.plugins = []

    def dispatch_build_menu_bar(self, menu):
        for plugin in self.plugins:
            plugin.on_build_menu_bar(menu)


@pytest.fixture
def window(qapp):
    win = QMainWindow()
    extra_tools_menu.build_extra_tools_menu(win)
    menu = plugin_menu.build_plugin_menu(win)
    win.plugin_manager = _Manager(win)
    win.plugin_manager.discover_and_load()
    plugin_menu.dispatch_plugin_menus(win, win.plugin_manager, menu)
    yield win
    win.deleteLater()


def _texts(menu: QMenu) -> list[str]:
    return [a.text() for a in menu.actions()]


def _plugins_menu(win) -> QMenu:
    return win.findChild(QMenu, plugin_menu.PLUGIN_MENU_OBJECT_NAME)


def _retouch(win) -> QMenu:
    return win.findChild(QMenu, extra_tools_menu.submenu_object_name("retouch_submenu"))


def test_plugin_menu_has_object_name(window):
    assert _plugins_menu(window) is window._plugin_menu


def test_dispatch_records_only_plugin_entries(window):
    recorded = sorted(a.text() for _c, a in window._plugin_menu_entries)
    assert recorded == [
        "Extra Tools entry", "Inside submenu", "Plain entry", "Plugin submenu", "Shared entry",
    ]


def test_remove_takes_every_recorded_entry_out(qapp, window):
    builtin = [t for t in _texts(_plugins_menu(window))
               if t not in ("Plain entry", "Plugin submenu")]
    retouch_before = [t for t in _texts(_retouch(window)) if t != "Extra Tools entry"]
    plugin_menu.remove_plugin_menu_entries(window)
    qapp.processEvents()
    assert _texts(_plugins_menu(window)) == builtin
    assert _texts(_retouch(window)) == retouch_before
    assert window._plugin_menu_entries == []
    plugin_menu.remove_plugin_menu_entries(window)   # a second call is a no-op


def test_reload_does_not_duplicate_entries(qapp, window, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    window.toast = SimpleNamespace(success=lambda _msg: None)
    before_plugins = _texts(_plugins_menu(window))
    before_retouch = _texts(_retouch(window))
    for _ in range(2):
        plugin_menu._reload_plugins(window)
        qapp.processEvents()
    assert window.plugin_manager.unloaded == 2
    assert _texts(_plugins_menu(window)) == before_plugins
    assert _texts(_retouch(window)) == before_retouch
    shared = next(
        m for m in _plugins_menu(window).findChildren(
            QMenu, options=Qt.FindChildOption.FindDirectChildrenOnly)
        if m.title() == "Plugin submenu"
    )
    assert _texts(shared) == ["Inside submenu", "Shared entry"]


def test_reload_declined_changes_nothing(qapp, window, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    entries = list(window._plugin_menu_entries)
    plugin_menu._reload_plugins(window)
    assert window.plugin_manager.unloaded == 0
    assert window._plugin_menu_entries == entries


def test_live_plugin_menu_falls_back_to_the_cached_wrapper(qapp):
    win = QMainWindow()
    try:
        menu = QMenu("Plugins", win)     # no object name
        win._plugin_menu = menu
        assert plugin_menu._live_plugin_menu(win) is menu
        del win._plugin_menu
        assert plugin_menu._live_plugin_menu(win) is None
    finally:
        win.deleteLater()
