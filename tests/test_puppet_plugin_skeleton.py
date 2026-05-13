"""Skeleton coverage for the built-in Puppet tab.

The Puppet workspace used to ship as a plugin under
``plugins/puppet/``; it now lives in-tree under ``Imervue/puppet/``
and the main window mounts it directly. These tests guard the
construction surface so later phases can extend without breaking
the contract.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QTabWidget

from Imervue.puppet import PuppetWorkspace


@pytest.mark.usefixtures("qapp")
def test_workspace_widget_builds():
    """Instantiating the workspace widget must succeed with no
    arguments and have a central widget."""
    widget = PuppetWorkspace()
    try:
        # PuppetWorkspace is a QMainWindow — central widget must exist.
        assert widget.centralWidget() is not None
    finally:
        widget.deleteLater()


@pytest.mark.usefixtures("qapp")
def test_workspace_mounts_into_qtabwidget():
    """The main window adds the workspace via ``QTabWidget.addTab``;
    that integration must succeed and leave a single, named tab."""
    workspace = PuppetWorkspace()
    tabs = QTabWidget()
    try:
        tabs.addTab(workspace, "Puppet")
        assert tabs.count() == 1
        assert tabs.tabText(0) == "Puppet"
    finally:
        tabs.deleteLater()


@pytest.mark.usefixtures("qapp")
def test_workspace_can_be_built_twice():
    """A repeated build pass must not leave residual state behind."""
    first = PuppetWorkspace()
    second = PuppetWorkspace()
    try:
        assert first is not second
        assert first.centralWidget() is not None
        assert second.centralWidget() is not None
    finally:
        first.deleteLater()
        second.deleteLater()
