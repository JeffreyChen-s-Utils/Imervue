"""UX-batch 2 tests: reset layout, recent files, status bar, shortcuts."""
from __future__ import annotations

import pytest

from Imervue.paint import recent_files, tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop(PaintWorkspace.DOCK_STATE_SETTING_KEY, None)
    user_setting_dict.pop(recent_files.RECENT_FILES_KEY, None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop(PaintWorkspace.DOCK_STATE_SETTING_KEY, None)
    user_setting_dict.pop(recent_files.RECENT_FILES_KEY, None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Reset layout
# ---------------------------------------------------------------------------


def test_reset_layout_clears_saved_state(qapp):
    ws = PaintWorkspace()
    try:
        ws._save_dock_state()  # noqa: SLF001
        assert PaintWorkspace.DOCK_STATE_SETTING_KEY in user_setting_dict
        ws.reset_workspace_layout()
        assert PaintWorkspace.DOCK_STATE_SETTING_KEY not in user_setting_dict
    finally:
        ws.deleteLater()


def test_reset_layout_makes_every_dock_visible(qapp):
    ws = PaintWorkspace()
    try:
        # Hide a dock first.
        ws._color_dock.setVisible(False)  # noqa: SLF001
        assert not ws._color_dock.isVisible()  # noqa: SLF001
        ws.reset_workspace_layout()
        assert ws._color_dock.isVisible()  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Recent files
# ---------------------------------------------------------------------------


def test_recent_files_add_dedupes_and_pushes_to_front():
    recent_files.add("/a/b/one.psd")
    recent_files.add("/a/b/two.psd")
    recent_files.add("/a/b/one.psd")
    paths = recent_files.paths()
    assert paths == ["/a/b/one.psd", "/a/b/two.psd"]


def test_recent_files_caps_at_max():
    for i in range(recent_files.RECENT_FILES_MAX + 5):
        recent_files.add(f"/p/{i}.psd")
    paths = recent_files.paths()
    assert len(paths) == recent_files.RECENT_FILES_MAX
    # Newest first.
    assert paths[0] == f"/p/{recent_files.RECENT_FILES_MAX + 4}.psd"


def test_recent_files_clear_drops_all():
    recent_files.add("/a/x.psd")
    recent_files.clear()
    assert recent_files.paths() == []


def test_recent_files_remove_drops_single_entry():
    recent_files.add("/a/keep.psd")
    recent_files.add("/b/drop.psd")
    recent_files.remove("/b/drop.psd")
    assert recent_files.paths() == ["/a/keep.psd"]


def test_recent_files_ignores_blank_path():
    recent_files.add("")
    recent_files.add(None)  # type: ignore[arg-type]
    assert recent_files.paths() == []


def test_recent_files_load_skips_garbage_entries():
    user_setting_dict[recent_files.RECENT_FILES_KEY] = [
        "/a/good.psd", 42, None, "", "/b/also-good.psd",
    ]
    paths = recent_files.paths()
    assert paths == ["/a/good.psd", "/b/also-good.psd"]


def test_file_menu_recent_submenu_shows_placeholder_when_empty(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge.refresh_recent_menu()
        actions = bridge._recent_menu.actions()  # noqa: SLF001
        assert len(actions) == 1
        assert actions[0].isEnabled() is False
    finally:
        ws.deleteLater()


def test_file_menu_recent_submenu_lists_added_paths(qapp):
    recent_files.add("/path/one.psd")
    recent_files.add("/path/two.psd")
    ws = PaintWorkspace()
    try:
        bridge = ws._file_menu_bridge   # noqa: SLF001
        bridge.refresh_recent_menu()
        # Every recent path + separator + Clear action.
        actions = [a for a in bridge._recent_menu.actions()      # noqa: SLF001
                   if not a.isSeparator()]
        labels = [a.text() for a in actions]
        # Most-recent first.
        assert labels[0].startswith("two.psd")
        assert labels[1].startswith("one.psd")
        # Trailing Clear entry.
        assert any("Clear" in label or "清除" in label for label in labels)
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------


def test_status_line_includes_zoom_size_and_layer(qapp):
    ws = PaintWorkspace()
    try:
        # Hover at known coords; the canvas already has a default
        # blank document so size + layer name are present.
        ws._on_hover_changed(5, 7)  # noqa: SLF001
        msg = ws._status.currentMessage()  # noqa: SLF001
        assert "5" in msg and "7" in msg
        assert "%" in msg  # zoom segment present
        assert "×" in msg  # canvas size segment present
    finally:
        ws.deleteLater()


def test_status_line_clears_when_cursor_leaves(qapp):
    ws = PaintWorkspace()
    try:
        ws._on_hover_changed(10, 20)  # noqa: SLF001
        assert ws._status.currentMessage()  # noqa: SLF001
        ws._on_hover_changed(-1, -1)  # noqa: SLF001
        assert ws._status.currentMessage() == ""  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Shortcuts cheat sheet
# ---------------------------------------------------------------------------


def test_collect_shortcut_rows_lists_known_bindings(qapp):
    from Imervue.paint.shortcuts_dialog import collect_shortcut_rows
    ws = PaintWorkspace()
    try:
        rows = collect_shortcut_rows(ws)
        # Every menu entry with a setShortcut must surface here.
        keys = {key for _label, key in rows}
        # File-menu bindings live across populate_file_menu.
        assert any(k == "Ctrl+N" for k in keys)
        assert any(k == "Ctrl+O" for k in keys)
        assert any(k == "Ctrl+S" for k in keys)
    finally:
        ws.deleteLater()


def test_shortcuts_dialog_constructs_with_rows(qapp):
    from Imervue.paint.shortcuts_dialog import ShortcutsDialog
    ws = PaintWorkspace()
    try:
        dialog = ShortcutsDialog(ws)
        try:
            assert dialog._table.rowCount() > 0  # noqa: SLF001
            assert dialog._table.columnCount() == 2  # noqa: SLF001
        finally:
            dialog.deleteLater()
    finally:
        ws.deleteLater()


def test_collect_shortcut_rows_dedupes(qapp):
    from Imervue.paint.shortcuts_dialog import collect_shortcut_rows
    ws = PaintWorkspace()
    try:
        rows = collect_shortcut_rows(ws)
        # Same (label, key) tuple should never appear twice.
        assert len(rows) == len(set(rows))
    finally:
        ws.deleteLater()
