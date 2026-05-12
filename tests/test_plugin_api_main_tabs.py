"""Tests for the ``on_build_main_tabs`` plugin hook + dispatcher.

The hook lets a plugin contribute a top-level tab to the main window's
``_main_tabs`` QTabWidget. The dispatcher in
``Imervue.integration_guide._dispatch_main_tab_hook`` walks
``manager.plugins`` and calls the hook on each one, defensively
wrapping each call so a buggy plugin doesn't tear down construction.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QLabel, QTabWidget

from Imervue.integration_guide import _dispatch_main_tab_hook
from Imervue.plugin.plugin_base import ImervuePlugin


class _GoodPlugin(ImervuePlugin):
    plugin_name = "Good"

    def __init__(self):  # noqa: D401 - test stub doesn't need ImervuePlugin's main_window
        self._calls = 0

    def on_build_main_tabs(self, tabs: QTabWidget) -> None:
        self._calls += 1
        tabs.addTab(QLabel("good"), "Good")


class _RaisingPlugin(ImervuePlugin):
    plugin_name = "Raising"

    def __init__(self):
        # Override the base ImervuePlugin __init__ so we can construct
        # the fake without a real ImervueMainWindow — the dispatcher
        # only reads ``plugin_name`` and ``on_build_main_tabs``.
        return

    def on_build_main_tabs(self, tabs: QTabWidget) -> None:
        del tabs
        raise RuntimeError("simulated shiboken-teardown failure")


class _ExplodingPlugin(ImervuePlugin):
    plugin_name = "Exploding"

    def __init__(self):
        # See ``_RaisingPlugin.__init__`` — the fake skips the base
        # class's main-window requirement on purpose.
        return

    def on_build_main_tabs(self, tabs: QTabWidget) -> None:
        del tabs
        raise ValueError("buggy plugin code")


def test_default_hook_is_a_noop(qapp):
    """The base class's hook must be silent by default — plugins that
    don't override it shouldn't perturb the dispatcher."""
    bare = ImervuePlugin.__new__(ImervuePlugin)
    tabs = QTabWidget()
    try:
        bare.on_build_main_tabs(tabs)  # must not raise
        assert tabs.count() == 0
    finally:
        tabs.deleteLater()


def test_dispatcher_calls_each_plugin_hook(qapp):
    plugin = _GoodPlugin()
    manager = SimpleNamespace(plugins=[plugin])
    tabs = QTabWidget()
    try:
        _dispatch_main_tab_hook(manager, tabs)  # NOSONAR — SimpleNamespace duck-types PluginManager here
        assert plugin._calls == 1   # noqa: SLF001
        assert tabs.count() == 1
        assert tabs.tabText(0) == "Good"
    finally:
        tabs.deleteLater()


def test_dispatcher_preserves_plugin_order(qapp):
    """Plugin tabs append in plugin discovery order — order matters
    so users can trust the layout."""
    a, b = _GoodPlugin(), _GoodPlugin()
    manager = SimpleNamespace(plugins=[a, b])
    tabs = QTabWidget()
    try:
        _dispatch_main_tab_hook(manager, tabs)  # NOSONAR — SimpleNamespace duck-types PluginManager here
        assert tabs.count() == 2
    finally:
        tabs.deleteLater()


def test_dispatcher_swallows_runtime_error(qapp, caplog):
    """A RuntimeError from one plugin must not block the rest — the
    same shiboken-teardown defence used in
    ``_append_plugin_languages``."""
    raising = _RaisingPlugin()
    healthy = _GoodPlugin()
    manager = SimpleNamespace(plugins=[raising, healthy])
    tabs = QTabWidget()
    try:
        with caplog.at_level(logging.WARNING, logger="Imervue.integration"):
            _dispatch_main_tab_hook(manager, tabs)  # NOSONAR — SimpleNamespace duck-types PluginManager here
        assert tabs.count() == 1   # only healthy one contributed
        assert any(
            "RuntimeError" in rec.message and "Raising" in rec.message
            for rec in caplog.records
        )
    finally:
        tabs.deleteLater()


def test_dispatcher_swallows_arbitrary_exceptions(qapp, caplog):
    """Plugin sandboxing covers any exception, not just RuntimeError —
    a buggy plugin can't crash startup."""
    exploding = _ExplodingPlugin()
    healthy = _GoodPlugin()
    manager = SimpleNamespace(plugins=[exploding, healthy])
    tabs = QTabWidget()
    try:
        with caplog.at_level(logging.ERROR, logger="Imervue.integration"):
            _dispatch_main_tab_hook(manager, tabs)  # NOSONAR — SimpleNamespace duck-types PluginManager here
        assert tabs.count() == 1
        assert any(
            "on_build_main_tabs" in rec.message and "Exploding" in rec.message
            for rec in caplog.records
        )
    finally:
        tabs.deleteLater()


def test_dispatcher_handles_empty_plugin_list(qapp):
    manager = SimpleNamespace(plugins=[])
    tabs = QTabWidget()
    try:
        # Must not raise.
        _dispatch_main_tab_hook(manager, tabs)  # NOSONAR — SimpleNamespace duck-types PluginManager here
        assert tabs.count() == 0
    finally:
        tabs.deleteLater()


@pytest.mark.parametrize("plugin_name", ["Good", "ImervuePlugin"])
def test_warning_uses_plugin_name_when_available(qapp, caplog, plugin_name):
    """The warning message names the plugin so the user can find the
    source — falls back to the class name when no plugin_name is set."""
    plugin = _RaisingPlugin()
    plugin.plugin_name = plugin_name
    manager = SimpleNamespace(plugins=[plugin])
    tabs = QTabWidget()
    try:
        with caplog.at_level(logging.WARNING, logger="Imervue.integration"):
            _dispatch_main_tab_hook(manager, tabs)  # NOSONAR — SimpleNamespace duck-types PluginManager here
        assert any(plugin_name in rec.message for rec in caplog.records)
    finally:
        tabs.deleteLater()
