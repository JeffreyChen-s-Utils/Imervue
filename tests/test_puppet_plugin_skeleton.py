"""Smoke tests for the built-in Puppet workspace.

The Puppet feature shipped first as a plugin (``plugins/puppet/``) and
later moved into the main package as ``Imervue.puppet``. This module
keeps the integration-surface coverage that the original plugin
skeleton tests provided: the workspace widget builds without a loaded
document, exposes a meaningful layout, and survives multiple
construction calls.
"""
from __future__ import annotations

import pytest


@pytest.mark.usefixtures("qapp")
def test_workspace_widget_builds():
    """Constructing :class:`PuppetWorkspace` with no arguments must
    succeed and produce a widget with a non-empty layout."""
    from Imervue.puppet.workspace import PuppetWorkspace

    workspace = PuppetWorkspace()
    try:
        layout = workspace.layout()
        if layout is not None:
            assert layout.count() >= 1
        # PuppetWorkspace is a QMainWindow — central widget must exist.
        assert workspace.centralWidget() is not None
    finally:
        workspace.deleteLater()


@pytest.mark.usefixtures("qapp")
def test_workspace_can_be_built_twice():
    """A repeated build pass must not leave residual state behind — the
    main window builds a single shared instance, but tests construct
    multiple to verify clean teardown."""
    from Imervue.puppet.workspace import PuppetWorkspace

    first = PuppetWorkspace()
    second = PuppetWorkspace()
    try:
        assert first is not second
        assert first.centralWidget() is not None
        assert second.centralWidget() is not None
    finally:
        first.deleteLater()
        second.deleteLater()
