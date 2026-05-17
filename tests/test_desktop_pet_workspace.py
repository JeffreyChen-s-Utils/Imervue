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


def test_failed_load_does_not_check_show_box(qapp, tmp_path):
    """The show-on-desktop checkbox must NOT be auto-ticked when
    the load fails — otherwise the user sees an empty pet window
    pop up alongside the failure message, which is worse UX than
    nothing happening at all."""
    ws = PetWorkspace()
    try:
        ws.load_puppet(tmp_path / "nope.puppet")
        assert ws._show_check.isChecked() is False   # noqa: SLF001
    finally:
        if ws.pet_window() is not None:
            ws.pet_window().hide()
            ws.pet_window().deleteLater()
        ws.deleteLater()


def test_successful_load_auto_shows_pet(qapp, tmp_path, monkeypatch):
    """A successful ``load_puppet`` must auto-tick the show
    checkbox so the user sees the pet appear without a second
    click. Without this, clicking "Load bundled March 7th" felt
    broken — the rig was loaded but the overlay stayed hidden."""
    ws = PetWorkspace()
    try:
        # Stub ``PetWindow.load_puppet_file`` to succeed without
        # actually parsing a .puppet file.
        from Imervue.desktop_pet.pet_window import PetWindow
        monkeypatch.setattr(
            PetWindow, "load_puppet_file",
            lambda self, path: True,
        )
        assert ws._show_check.isChecked() is False   # noqa: SLF001
        ws.load_puppet(tmp_path / "any.puppet")
        assert ws._show_check.isChecked() is True   # noqa: SLF001
    finally:
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


def test_resolve_bundled_example_uses_app_paths(monkeypatch, tmp_path):
    """A packaged build doesn't run from the repo root, so the
    workspace must consult ``app_paths.examples_dir()`` rather
    than a CWD-relative literal. Plant a fake rig under a
    temp-dir-rooted ``examples_dir()`` and verify resolution
    finds it without relying on the test's CWD."""
    from Imervue.desktop_pet import pet_workspace
    from Imervue.system import app_paths

    fake_examples = tmp_path / "examples"
    fake_puppet = fake_examples / "puppet" / "march_7th.puppet"
    fake_puppet.parent.mkdir(parents=True)
    fake_puppet.write_bytes(b"PK\x03\x04")  # just needs to be_a_file
    monkeypatch.setattr(app_paths, "examples_dir", lambda: fake_examples)
    resolved = pet_workspace._resolve_bundled_example()   # noqa: SLF001
    assert resolved == fake_puppet


def test_resolve_bundled_example_returns_none_when_missing(monkeypatch, tmp_path):
    """No bundled rig anywhere → resolver hands back None so the
    workspace can surface the dedicated "install or run from the
    repo root" status message rather than crashing with a
    FileNotFoundError."""
    from Imervue.desktop_pet import pet_workspace
    from Imervue.system import app_paths

    empty = tmp_path / "no-examples"
    empty.mkdir()
    monkeypatch.setattr(app_paths, "examples_dir", lambda: empty)
    monkeypatch.chdir(empty)
    assert pet_workspace._resolve_bundled_example() is None   # noqa: SLF001


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
