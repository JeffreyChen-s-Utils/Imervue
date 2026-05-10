"""Phase 0 skeleton coverage for the Puppet plugin.

The plugin currently ships a placeholder tab; later phases fill in the
file format, renderer, mesh editor, parameter rig, motion timeline,
physics, and runtime tracking. These tests guard the integration
surface (tab installs, title resolves, placeholder widget builds) so
later phases can extend without breaking the contract.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QTabWidget


def test_placeholder_widget_builds(qapp):
    from puppet.puppet_plugin import _build_placeholder_widget

    widget = _build_placeholder_widget()
    try:
        # Headline + subtitle = two visible labels
        labels = widget.findChildren(type(widget).__bases__[0])  # noqa: SLF001
        assert widget.layout() is not None
        assert widget.layout().count() == 2
        del labels
    finally:
        widget.deleteLater()


def test_plugin_adds_tab_to_main_tabs(qapp):
    from puppet.puppet_plugin import PuppetPlugin

    fake_main = SimpleNamespace(viewer=SimpleNamespace())
    plugin = PuppetPlugin(fake_main)
    tabs = QTabWidget()
    try:
        plugin.on_build_main_tabs(tabs)
        assert tabs.count() == 1
        assert tabs.tabText(0)   # non-empty (Polygon / 偶動畫 / etc. — locale dependent)
    finally:
        tabs.deleteLater()


def test_plugin_uses_localised_tab_title(qapp, monkeypatch):
    """When ``puppet_tab_title`` is registered for the active locale the
    tab adopts that label; no key → fallback to ``Puppet``."""
    from Imervue.multi_language.language_wrapper import language_wrapper
    from puppet.puppet_plugin import PuppetPlugin

    monkeypatch.setitem(
        language_wrapper.language_word_dict, "puppet_tab_title", "TestPuppet",
    )
    fake_main = SimpleNamespace(viewer=SimpleNamespace())
    plugin = PuppetPlugin(fake_main)
    tabs = QTabWidget()
    try:
        plugin.on_build_main_tabs(tabs)
        assert tabs.tabText(0) == "TestPuppet"
    finally:
        tabs.deleteLater()


def test_plugin_metadata_present():
    """plugin_name / version / description / author must be set so the
    plugin manager UI can list this plugin meaningfully."""
    from puppet.puppet_plugin import PuppetPlugin

    assert PuppetPlugin.plugin_name == "Puppet"
    assert PuppetPlugin.plugin_version
    assert PuppetPlugin.plugin_description
    assert PuppetPlugin.plugin_author


def test_plugin_class_export():
    """``plugins/puppet/__init__.py`` must expose ``plugin_class`` so the
    plugin manager can instantiate it via the standard discovery path."""
    import puppet
    from puppet.puppet_plugin import PuppetPlugin

    assert puppet.plugin_class is PuppetPlugin
