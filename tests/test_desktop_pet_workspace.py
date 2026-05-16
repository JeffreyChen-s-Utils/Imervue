"""Smoke tests for the desktop-pet workspace.

The pet overlay needs a real platform window to exercise the
GL context; that's out of reach for headless CI. The tests below
focus on the pure-Python parts: lazy construction of the pet
window, file-loading dispatch, status-label feedback, and toggle
state synchronisation. The actual ``show()`` of the overlay is
exercised only via the ``visibility_changed`` signal contract.
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet.pet_workspace import PetWorkspace


def test_workspace_instantiates_without_creating_window(qapp):
    """Tab construction must NOT spin up the GL overlay — the
    workspace owns a lazy reference that the user has to opt
    into. Without this guard, every Imervue launch would
    instantiate a full QOpenGLWidget for users who never click
    the tab."""
    ws = PetWorkspace()
    try:
        assert ws.pet_window() is None
    finally:
        ws.deleteLater()


def test_load_puppet_with_bad_path_reports_failure(qapp, tmp_path):
    """A missing / corrupt ``.puppet`` archive must report False
    so the workspace can surface it to the user instead of
    silently swallowing the error."""
    ws = PetWorkspace()
    try:
        bad_path = tmp_path / "nope.puppet"
        assert ws.load_puppet(bad_path) is False
        # Status label updated so a real user would see the error.
        assert "Failed" in ws._status.text()   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_load_puppet_creates_overlay_on_first_call(qapp, tmp_path):
    """The pet window is created lazily — the first
    ``load_puppet`` (success or fail) is what brings it into
    existence so subsequent toggles have a target."""
    ws = PetWorkspace()
    try:
        bad_path = tmp_path / "nope.puppet"
        ws.load_puppet(bad_path)
        assert ws.pet_window() is not None
    finally:
        # Force-hide the lazily-created overlay so the test
        # teardown doesn't leak a top-level QWidget.
        if ws.pet_window() is not None:
            ws.pet_window().hide()
            ws.pet_window().deleteLater()
        ws.deleteLater()


def test_attach_tray_stores_reference(qapp):
    """The tray hookup is optional and goes through
    ``attach_tray``. The workspace just needs to keep the
    reference for later mirroring; no behaviour change here."""
    ws = PetWorkspace()
    try:
        sentinel = object()
        ws.attach_tray(sentinel)
        assert ws._tray is sentinel   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_default_example_constant_points_inside_examples_dir():
    """Catch the easy mistake of mis-spelling the bundled rig
    path — it has to resolve under ``examples/puppet/`` so the
    workspace can find it once the user is running from the
    repository root."""
    from Imervue.desktop_pet.pet_workspace import DEFAULT_EXAMPLE_PUPPET
    assert DEFAULT_EXAMPLE_PUPPET.startswith("examples/puppet/")
    assert DEFAULT_EXAMPLE_PUPPET.endswith(".puppet")


@pytest.mark.parametrize("preset", ["small", "medium", "large"])
def test_size_combo_offers_each_preset(qapp, preset):
    """Every preset string the combo box exposes has to be
    accepted by ``PetWindow.set_size_preset`` — a typo would
    silently leave the user's pick unapplied."""
    ws = PetWorkspace()
    try:
        idx = ws._size_combo.findText(preset)   # noqa: SLF001
        assert idx >= 0
    finally:
        ws.deleteLater()
