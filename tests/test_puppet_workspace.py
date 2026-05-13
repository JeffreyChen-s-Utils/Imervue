"""Tests for the PuppetWorkspace widget — toolbar, recent menu,
open dialog wiring, status label.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Imervue.puppet.document import Drawable, PuppetDocument
from Imervue.puppet.document_io import save_puppet
from Imervue.puppet.workspace import PuppetWorkspace, _push_recent
from Imervue.user_settings.user_setting_dict import user_setting_dict


_TINY_PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "8900000016624B47440000000000000000000000000000000000000000000000"
    "00FFA600007AC9000000097048597300000B1300000B13"
    "01009A9C180000000774494D4507E5050C0E2A2F"
    "F2C99B6F0000000A4944415408D763F8FFFF3F0005FE02FED832FA610000"
    "000049454E44AE426082"
)


def _write_minimal_puppet(path: Path) -> None:
    doc = PuppetDocument(size=(64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            indices=[0, 1, 2],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            draw_order=0,
        ),
    ]
    save_puppet(doc, path)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_workspace_constructs_with_no_document(qapp):
    ws = PuppetWorkspace()
    try:
        assert ws.canvas() is not None
        # The toolbar exposes Open / Recent / Fit; layout count includes
        # toolbar + canvas + status, in some order.
        assert ws.layout().count() >= 3
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Open puppet
# ---------------------------------------------------------------------------


def test_open_puppet_loads_into_canvas(qapp, tmp_path):
    out = tmp_path / "tiny.puppet"
    _write_minimal_puppet(out)
    ws = PuppetWorkspace()
    try:
        assert ws.open_puppet(out) is True
        assert ws.canvas().document() is not None
        assert len(ws.canvas().document().drawables) == 1
    finally:
        ws.deleteLater()


def test_open_puppet_sets_status_on_success(qapp, tmp_path):
    out = tmp_path / "tiny.puppet"
    _write_minimal_puppet(out)
    ws = PuppetWorkspace()
    try:
        ws.open_puppet(out)
        assert "tiny.puppet" in ws._status.text()   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_open_puppet_returns_false_on_corrupt_file(qapp, tmp_path):
    bad = tmp_path / "broken.puppet"
    bad.write_bytes(b"not a zip")
    ws = PuppetWorkspace()
    try:
        assert ws.open_puppet(bad) is False
        # Status reflects the failure
        assert "Failed" in ws._status.text() or "error" in ws._status.text().lower()  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_open_puppet_returns_false_on_missing_file(qapp, tmp_path):
    ws = PuppetWorkspace()
    try:
        assert ws.open_puppet(tmp_path / "absent.puppet") is False
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Recent files
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_recent():
    """The autouse ``_isolate_user_settings`` fixture in conftest already
    redirects user_setting.json; here we just clear the puppet-specific
    key between tests so no list leaks across cases."""
    user_setting_dict.pop("puppet_recent_files", None)
    yield
    user_setting_dict.pop("puppet_recent_files", None)


def test_recent_pushes_in_lru_order():
    _push_recent("a.puppet")
    _push_recent("b.puppet")
    _push_recent("a.puppet")   # re-touch promotes to front
    assert user_setting_dict["puppet_recent_files"] == ["a.puppet", "b.puppet"]


def test_recent_truncates_to_limit():
    for i in range(20):
        _push_recent(f"p{i}.puppet")
    assert len(user_setting_dict["puppet_recent_files"]) == 10
    # Most-recent first
    assert user_setting_dict["puppet_recent_files"][0] == "p19.puppet"


def test_open_puppet_records_into_recent_list(qapp, tmp_path):
    out = tmp_path / "kept.puppet"
    _write_minimal_puppet(out)
    ws = PuppetWorkspace()
    try:
        ws.open_puppet(out)
        assert str(out) in user_setting_dict["puppet_recent_files"]
    finally:
        ws.deleteLater()


def test_recent_menu_prunes_missing_files(qapp, tmp_path):
    user_setting_dict["puppet_recent_files"] = [
        str(tmp_path / "gone.puppet"),
    ]
    ws = PuppetWorkspace()
    try:
        ws._rebuild_recent_menu()   # noqa: SLF001
        # The non-existent path drops out of the persisted list
        assert user_setting_dict["puppet_recent_files"] == []
        # The menu shows a disabled "(empty)" entry
        action = ws._recent_menu.actions()[0]   # noqa: SLF001
        assert not action.isEnabled()
    finally:
        ws.deleteLater()


def test_recent_menu_lists_existing_files(qapp, tmp_path):
    out = tmp_path / "alive.puppet"
    _write_minimal_puppet(out)
    user_setting_dict["puppet_recent_files"] = [str(out)]
    ws = PuppetWorkspace()
    try:
        ws._rebuild_recent_menu()   # noqa: SLF001
        actions = ws._recent_menu.actions()   # noqa: SLF001
        assert len(actions) == 1
        assert actions[0].text() == "alive.puppet"
        assert actions[0].toolTip() == str(out)
        assert actions[0].isEnabled()
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Examples submenu — auto-populated from <app_dir>/examples/puppet/
# ---------------------------------------------------------------------------


def test_examples_menu_lists_bundled_puppets(qapp, tmp_path, monkeypatch):
    """``_rebuild_examples_menu`` must scan
    ``<examples_dir>/puppet/*.puppet`` and add one action per file.
    File names are pretty-printed (underscores → spaces, title-cased)
    so ``march_7th.puppet`` shows as ``March 7Th``."""
    import Imervue.puppet.workspace as ws_mod
    examples_root = tmp_path / "examples"
    (examples_root / "puppet").mkdir(parents=True)
    _write_minimal_puppet(examples_root / "puppet" / "march_7th.puppet")
    _write_minimal_puppet(examples_root / "puppet" / "demo_rig.puppet")
    monkeypatch.setattr(
        "Imervue.system.app_paths.app_dir",
        lambda: tmp_path,
    )

    ws = ws_mod.PuppetWorkspace()
    try:
        ws._rebuild_examples_menu()   # noqa: SLF001
        actions = ws._examples_menu.actions()   # noqa: SLF001
        labels = [a.text() for a in actions if a.isEnabled()]
        # Sorted alphabetically by stem, pretty-printed.
        assert labels == ["Demo Rig", "March 7Th"]
        # Tooltip carries the absolute path.
        assert "march_7th.puppet" in actions[1].toolTip()
    finally:
        ws.deleteLater()


def test_examples_menu_shows_disabled_placeholder_when_empty(
    qapp, tmp_path, monkeypatch,
):
    """When the examples directory is missing or empty, the menu
    contains a single disabled placeholder so the user understands
    that nothing was bundled rather than silently showing no menu."""
    import Imervue.puppet.workspace as ws_mod
    # No examples/puppet/ directory at all under tmp_path.
    monkeypatch.setattr(
        "Imervue.system.app_paths.app_dir",
        lambda: tmp_path,
    )

    ws = ws_mod.PuppetWorkspace()
    try:
        ws._rebuild_examples_menu()   # noqa: SLF001
        actions = ws._examples_menu.actions()   # noqa: SLF001
        assert len(actions) == 1
        assert not actions[0].isEnabled()
    finally:
        ws.deleteLater()


def test_examples_menu_action_loads_via_open_puppet(
    qapp, tmp_path, monkeypatch,
):
    """Clicking an entry must call ``open_puppet(path)`` with the
    absolute path of the bundled file. The shipped rig should then
    end up bound to the canvas."""
    import Imervue.puppet.workspace as ws_mod
    examples_root = tmp_path / "examples"
    (examples_root / "puppet").mkdir(parents=True)
    target = examples_root / "puppet" / "tiny.puppet"
    _write_minimal_puppet(target)
    monkeypatch.setattr(
        "Imervue.system.app_paths.app_dir",
        lambda: tmp_path,
    )

    ws = ws_mod.PuppetWorkspace()
    try:
        ws._rebuild_examples_menu()   # noqa: SLF001
        actions = [
            a for a in ws._examples_menu.actions()   # noqa: SLF001
            if a.isEnabled()
        ]
        assert len(actions) == 1
        actions[0].trigger()
        assert ws.canvas().document() is not None
    finally:
        ws.deleteLater()
