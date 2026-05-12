"""Skeleton coverage for the Puppet plugin.

The plugin lives under ``plugins/puppet/`` and contributes the Puppet
top-level tab via ``on_build_main_tabs``. These tests guard the
integration surface (plugin adds tab, workspace widget builds) so
later phases can extend without breaking the contract.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QTabWidget


@pytest.mark.usefixtures("qapp")
def test_workspace_widget_builds():
    """Instantiating the workspace widget must succeed with no
    arguments and produce a layout with at least one child."""
    from puppet.puppet_plugin import _build_workspace_widget

    widget = _build_workspace_widget()
    try:
        # PuppetWorkspace is a QMainWindow — central widget must exist.
        assert widget.centralWidget() is not None
    finally:
        widget.deleteLater()


@pytest.mark.usefixtures("qapp")
def test_plugin_adds_tab_to_main_tabs():
    """``on_build_main_tabs`` must add exactly one non-empty tab."""
    from puppet.puppet_plugin import PuppetPlugin

    fake_main = SimpleNamespace(viewer=SimpleNamespace())
    plugin = PuppetPlugin(fake_main)
    tabs = QTabWidget()
    try:
        plugin.on_build_main_tabs(tabs)
        assert tabs.count() == 1
        # Tab title is locale-dependent (Puppet / 偶動畫 / etc.); only
        # require it to resolve to non-empty.
        assert tabs.tabText(0)
    finally:
        tabs.deleteLater()


@pytest.mark.usefixtures("qapp")
def test_workspace_can_be_built_twice():
    """A repeated build pass must not leave residual state behind."""
    from puppet.workspace import PuppetWorkspace

    first = PuppetWorkspace()
    second = PuppetWorkspace()
    try:
        assert first is not second
        assert first.centralWidget() is not None
        assert second.centralWidget() is not None
    finally:
        first.deleteLater()
        second.deleteLater()
