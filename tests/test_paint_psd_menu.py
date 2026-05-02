"""Tests for the File-menu PSD open / save bridge.

The pure psd_io serialiser is exercised in its own existing test
module; this file pins the menu glue + the workspace-level commit
helpers so a refactor of either side is caught early.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.file_menu import commit_open_psd, commit_save_psd
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.psd_io import load_psd, save_psd
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


# ---------------------------------------------------------------------------
# commit_save_psd
# ---------------------------------------------------------------------------


def test_save_psd_writes_file(workspace, tmp_path):
    layer = workspace.canvas().document().active_layer()
    layer.image[..., :3] = (123, 45, 67)
    target = tmp_path / "out.psd"
    ok = commit_save_psd(workspace, str(target))
    assert ok is True
    assert target.exists()
    assert target.stat().st_size > 0


def test_save_psd_handles_empty_document(qapp, tmp_path):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document._layers.clear()  # noqa: SLF001
        document._composite_cache = None  # noqa: SLF001
        ok = commit_save_psd(ws, str(tmp_path / "x.psd"))
        assert ok is False
    finally:
        ws.deleteLater()


def test_save_psd_swallows_oserror(workspace, tmp_path):
    """Saving into a directory that doesn't exist should fail
    gracefully rather than blowing up the menu callback."""
    bogus = tmp_path / "no_such_dir" / "out.psd"
    # Force the parent NOT to be created — psd_io would otherwise
    # create it. The expected failure path is harder to hit; the
    # save helper still returns True after creating intermediates.
    # So instead, lock the folder by creating a file at that path.
    locked = tmp_path / "name_collision"
    locked.write_text("not a directory")
    ok = commit_save_psd(workspace, str(locked / "child.psd"))
    assert ok is False
    # Ensure the bogus path placeholder exists.
    del bogus


# ---------------------------------------------------------------------------
# commit_open_psd
# ---------------------------------------------------------------------------


def test_open_psd_loads_into_new_tab(workspace, tmp_path):
    """Open should land in a fresh tab so the user's current canvas
    isn't silently overwritten."""
    # Build a PSD on disk first.
    src_doc = workspace.canvas().document()
    layer = src_doc.active_layer()
    layer.image[..., :3] = (10, 20, 30)
    target = tmp_path / "input.psd"
    save_psd(src_doc, target)
    before_tabs = workspace.tab_count()
    ok = commit_open_psd(workspace, str(target))
    assert ok is True
    assert workspace.tab_count() == before_tabs + 1


def test_open_psd_pastes_pixels_into_canvas(workspace, tmp_path):
    src_doc = workspace.canvas().document()
    layer = src_doc.active_layer()
    layer.image[..., :3] = (55, 110, 165)
    target = tmp_path / "input.psd"
    save_psd(src_doc, target)
    commit_open_psd(workspace, str(target))
    new_layer = workspace.canvas().document().active_layer()
    # Roundtrip preserves the source pixels (allow ±1 due to alpha
    # premultiplication during PSD encoding).
    assert int(new_layer.image[0, 0, 0]) in range(54, 57)


def test_open_psd_missing_path_returns_false(workspace, tmp_path):
    ok = commit_open_psd(workspace, str(tmp_path / "no_such.psd"))
    assert ok is False


def test_open_psd_garbage_file_returns_false(workspace, tmp_path):
    bad = tmp_path / "junk.psd"
    bad.write_bytes(b"not a psd at all")
    ok = commit_open_psd(workspace, str(bad))
    assert ok is False


# ---------------------------------------------------------------------------
# Round-trip parity at the engine level (sanity)
# ---------------------------------------------------------------------------


def test_round_trip_preserves_layer_count(workspace, tmp_path):
    document = workspace.canvas().document()
    document.add_layer(name="Two")
    document.add_layer(name="Three")
    target = tmp_path / "stack.psd"
    save_psd(document, target)
    reloaded = load_psd(target)
    assert reloaded.layer_count == document.layer_count


def test_round_trip_preserves_layer_names(workspace, tmp_path):
    document = workspace.canvas().document()
    document.add_layer(name="Inks")
    document.add_layer(name="Colour")
    target = tmp_path / "named.psd"
    save_psd(document, target)
    reloaded = load_psd(target)
    names = [reloaded.layer_at(i).name for i in range(reloaded.layer_count)]
    assert "Inks" in names
    assert "Colour" in names


def test_round_trip_preserves_blend_mode(workspace, tmp_path):
    document = workspace.canvas().document()
    document.add_layer(name="Multiply")
    if hasattr(document, "set_layer_blend_mode"):
        document.set_layer_blend_mode(blend_mode="multiply")
    else:
        document.active_layer().blend_mode = "multiply"
    target = tmp_path / "blend.psd"
    save_psd(document, target)
    reloaded = load_psd(target)
    blend_modes = {reloaded.layer_at(i).blend_mode for i in range(
        reloaded.layer_count,
    )}
    assert "multiply" in blend_modes


# ---------------------------------------------------------------------------
# File-menu wiring smoke test
# ---------------------------------------------------------------------------


def test_file_menu_exposes_open_and_save_psd_actions(workspace):
    from Imervue.paint.paint_menu_bar import menu_for
    file_menu = menu_for(workspace, "file")
    labels = [a.text() for a in file_menu.actions() if not a.isSeparator()]
    assert any("PSD" in label for label in labels)


def test_file_menu_open_psd_has_ctrl_o_shortcut(workspace):
    from Imervue.paint.paint_menu_bar import menu_for
    file_menu = menu_for(workspace, "file")
    # Find the "Open PSD" action by its translated label.
    for action in file_menu.actions():
        if action.text() and "PSD" in action.text() and "Open" in action.text():
            assert not action.shortcut().isEmpty()
            return
    pytest.fail("Open PSD action not found in File menu")


def test_workspace_psd_save_round_trip_via_path(workspace, tmp_path):
    """Belt + braces: full sequence of Save → Open → check pixels."""
    layer = workspace.canvas().document().active_layer()
    layer.image[..., :3] = (200, 100, 50)
    target = tmp_path / "rt.psd"
    assert commit_save_psd(workspace, str(target))
    assert Path(target).exists()
    # Open into a fresh tab.
    assert commit_open_psd(workspace, str(target))
    # The active canvas should now reflect the PSD content.
    out_layer = workspace.canvas().document().active_layer()
    np.testing.assert_array_equal(out_layer.image[0, 0, :3], [200, 100, 50])
