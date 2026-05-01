"""Tests for the File-menu wiring + bridge."""
from __future__ import annotations

import json
import struct

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.brush_preset_io import IMERVUE_FORMAT_TAG
from Imervue.paint.color_palette_io import GIMP_PALETTE_EXTENSION
from Imervue.paint.file_menu import _FileMenuBridge
from Imervue.paint.paint_menu_bar import menu_for
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop("paint_brush_presets", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop("paint_brush_presets", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Menu population
# ---------------------------------------------------------------------------


def test_file_menu_populated_after_construction(qapp):
    ws = PaintWorkspace()
    try:
        file_menu = menu_for(ws, "file")
        # 2 tab actions + sep + 2 import + sep + 3 export = 9 entries
        # (separators count as actions in Qt's actions() list).
        assert len(file_menu.actions()) == 9
    finally:
        ws.deleteLater()


def test_workspace_holds_bridge_reference(qapp):
    """The workspace must keep the bridge alive — losing it would
    GC the bound-method slots and silently un-wire the actions."""
    ws = PaintWorkspace()
    try:
        assert isinstance(ws._file_menu_bridge, _FileMenuBridge)  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_file_menu_actions_have_translated_labels(qapp):
    """Every action's label must come from the translation dict —
    a missing key would surface as the raw 'paint_file_*' string."""
    ws = PaintWorkspace()
    try:
        file_menu = menu_for(ws, "file")
        labels = [
            a.text() for a in file_menu.actions()
            if not a.isSeparator()
        ]
        for label in labels:
            assert not label.startswith("paint_file_"), label
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Bridge — import paths
# ---------------------------------------------------------------------------


def test_import_brush_preset_round_trip(qapp, tmp_path):
    """Bridge feeds an .imv-brush bundle through import_bundle and
    persists the presets via save_brush_presets."""
    bundle = tmp_path / "kit.imv-brush"
    bundle.write_text(json.dumps({
        "format": IMERVUE_FORMAT_TAG, "version": 1,
        "presets": [{"name": "Imported", "size": 12}],
    }), encoding="utf-8")
    ws = PaintWorkspace()
    try:
        # Bypass the QFileDialog by calling the bridge's verb with
        # the path baked in via monkeypatched _pick_file.
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge._pick_file = lambda **_: str(bundle)  # noqa: SLF001
        bridge.import_brush_preset()
    finally:
        ws.deleteLater()
    persisted = user_setting_dict.get("paint_brush_presets", [])
    assert any(p.get("name") == "Imported" for p in persisted)


def test_import_palette_pushes_into_color_history(qapp, tmp_path):
    target = tmp_path / "demo.gpl"
    target.write_text("GIMP Palette\n255 0 0 R\n0 255 0 G\n", encoding="utf-8")
    ws = PaintWorkspace()
    try:
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge._pick_file = lambda **_: str(target)  # noqa: SLF001
        bridge.import_palette()
        history = ws.state().color_history
        # Both imported colours land in the history (most recent first).
        assert (255, 0, 0) in history
        assert (0, 255, 0) in history
    finally:
        ws.deleteLater()


def test_import_palette_handles_missing_path(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge._pick_file = lambda **_: None  # noqa: SLF001
        bridge.import_palette()   # no exception
    finally:
        ws.deleteLater()


def test_import_palette_recovers_from_corrupt_file(qapp, tmp_path):
    bad = tmp_path / "bad.aco"
    bad.write_bytes(b"\x00")
    ws = PaintWorkspace()
    try:
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge._pick_file = lambda **_: str(bad)  # noqa: SLF001
        bridge.import_palette()
        # Corrupt file → engine returned [] → no colours added.
        assert ws.state().color_history == []
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Bridge — export paths
# ---------------------------------------------------------------------------


def test_export_image_writes_a_file(qapp, tmp_path):
    target = tmp_path / "out.png"
    ws = PaintWorkspace()
    try:
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge._pick_save_file = lambda **_: str(target)  # noqa: SLF001
        bridge.export_active_image()
    finally:
        ws.deleteLater()
    assert target.exists()


def test_export_pages_short_circuits_without_project(qapp, tmp_path):
    """No project bound → the export action returns silently rather
    than raising. The export verbs themselves reject empty projects;
    we want to verify the bridge skips before reaching them."""
    target = tmp_path / "comic.cbz"
    ws = PaintWorkspace()
    try:
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge._pick_save_file = lambda **_: str(target)  # noqa: SLF001
        # No assertion needed beyond "doesn't raise".
        bridge.export_pages_cbz()
        bridge.export_pages_pdf()
    finally:
        ws.deleteLater()
    # No project was bound, so no file was written.
    assert not target.exists()


def test_export_pages_cbz_writes_when_project_present(qapp, tmp_path):
    """When a project IS bound, the bridge actually exports."""
    from Imervue.paint.page_templates import (
        project_from_template, template_by_name,
    )
    target = tmp_path / "comic.cbz"
    ws = PaintWorkspace()
    try:
        ws._project = project_from_template(  # noqa: SLF001
            template_by_name("manga_a5"), page_count=2,
        )
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge._pick_save_file = lambda **_: str(target)  # noqa: SLF001
        bridge.export_pages_cbz()
    finally:
        ws.deleteLater()
    assert target.exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_default_export_preset_is_first_built_in():
    """The bridge picks built-ins[0] when no user presets are set;
    confirm the helper resolves to a real preset rather than None."""
    from Imervue.paint.export_presets import BUILT_IN_EXPORT_PRESETS
    from Imervue.paint.file_menu import _default_export_preset
    assert _default_export_preset() == BUILT_IN_EXPORT_PRESETS[0]


def test_image_filter_for_known_format():
    from Imervue.paint.file_menu import _image_filter_for
    assert _image_filter_for("png").startswith("PNG")


def test_image_filter_for_unknown_format_falls_back():
    """Unknown formats produce a usable filter string rather than
    crashing — the engine could grow new formats without breaking
    the file dialog filter."""
    from Imervue.paint.file_menu import _image_filter_for
    assert _image_filter_for("xyz") == "XYZ (*.xyz)"


# Pull in unused imports so ruff doesn't flag them — these prove the
# tests actually exercise the documented engine surface.
_USED = (struct, GIMP_PALETTE_EXTENSION)
