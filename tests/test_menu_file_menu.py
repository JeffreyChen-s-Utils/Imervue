"""Characterisation tests for ``Imervue.menu.file_menu.build_file_menu``.

Pins the File and Tile Size menus' entry order, separators, check state and
the callbacks each entry triggers, so restructuring the builder cannot drop,
reorder or rewire an entry.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QMainWindow

from Imervue.menu import file_menu as fm
from Imervue.multi_language.language_wrapper import language_wrapper


class _StubMainWindow(QMainWindow):
    """Main-window stand-in exposing only what the builder touches."""

    def __init__(self, thumbnail_size=256, tile_padding=8):
        super().__init__()
        self.viewer = SimpleNamespace(thumbnail_size=thumbnail_size, tile_padding=tile_padding)
        self.clipboard_monitor = None
        self.calls: list[tuple] = []

    def change_tile_size(self, size):
        self.calls.append(("tile_size", size))

    def set_browse_mode(self, mode):
        self.calls.append(("browse_mode", mode))

    def change_tile_padding(self, pad):
        self.calls.append(("tile_padding", pad))


@pytest.fixture
def window(qapp):
    win = _StubMainWindow()
    yield win
    win.deleteLater()


def _texts(menu):
    return [a.text() for a in menu.actions()]


def _lang(key, fallback=None):
    return language_wrapper.language_word_dict.get(key, fallback)


def test_returns_file_menu_and_adds_two_top_level_menus(window):
    menu = fm.build_file_menu(window)
    titles = [a.text() for a in window.menuBar().actions()]
    assert titles == [_lang("main_window_current_file"), _lang("main_window_tile_size")]
    assert menu.title() == titles[0]


def test_file_menu_entries_in_order(window):
    texts = _texts(fm.build_file_menu(window))
    expected = [
        _lang("menu_new_window", "New Window"), "",
        _lang("main_window_open_image"), _lang("main_window_open_folder"),
        _lang("recent_menu_title", "Recent"),
        _lang("bookmark_title", "Bookmarks"), _lang("tag_album_title", "Tags & Albums"), "",
        _lang("recycle_bin_title", "Recycle Bin"), _lang("main_window_remove_undo_stack"), "",
        _lang("file_menu_paste_clipboard", "Paste from Clipboard"),
        _lang("file_menu_clipboard_monitor", "Auto-annotate Clipboard Images"), "",
    ]
    if sys.platform == "win32":
        expected.append(_lang("file_assoc_menu", "File Association"))
    expected += [
        "",
        _lang("session_menu", "Session"), _lang("workspace_menu", "Workspaces…"),
        _lang("ext_editor_menu", "External Editors…"),
        _lang("ext_editor_open_in", "Open in External Editor"), "",
        _lang("shortcut_title", "Keyboard Shortcuts"), _lang("preferences_title", "Preferences"),
        _lang("profiles_title", "Profiles…"), "",
        _lang("main_window_exit"),
    ]
    assert texts == expected


def test_clipboard_monitor_entry_reflects_monitor_state(qapp):
    win = _StubMainWindow()
    win.clipboard_monitor = SimpleNamespace(is_enabled=lambda: True)
    try:
        menu = fm.build_file_menu(win)
        monitor = next(a for a in menu.actions() if a.text() == _lang(
            "file_menu_clipboard_monitor", "Auto-annotate Clipboard Images"))
        assert monitor.isCheckable()
        assert monitor.isChecked()
    finally:
        win.deleteLater()


def test_file_entries_trigger_their_handlers(window, monkeypatch):
    seen = []
    for name in ("open_image", "open_folder", "_open_bookmarks", "_open_preferences"):
        monkeypatch.setattr(fm, name, lambda ui, n=name: seen.append((n, ui)))
    menu = fm.build_file_menu(window)
    by_text = {a.text(): a for a in menu.actions()}
    for key in ("main_window_open_image", "main_window_open_folder"):
        by_text[_lang(key)].trigger()
    by_text[_lang("bookmark_title", "Bookmarks")].trigger()
    by_text[_lang("preferences_title", "Preferences")].trigger()
    assert seen == [("open_image", window), ("open_folder", window),
                    ("_open_bookmarks", window), ("_open_preferences", window)]


def test_session_submenu_entries(window):
    menu = fm.build_file_menu(window)
    session = next(a.menu() for a in menu.actions()
                   if a.text() == _lang("session_menu", "Session"))
    assert _texts(session) == [_lang("session_save", "Save Session…"),
                               _lang("session_load", "Load Session…")]


def _view_menu(window):
    fm.build_file_menu(window)
    return window.menuBar().actions()[1].menu()


def test_view_menu_tile_sizes_then_submenus(window):
    texts = _texts(_view_menu(window))
    assert texts == ["128 x 128", "256 x 256", "512 x 512", "1024 x 1024", "None", "",
                     _lang("view_browse_mode", "Browse Mode"), "",
                     _lang("view_tile_density", "Thumbnail Density")]


def test_view_menu_checks_active_tile_size_and_triggers_change(window):
    actions = _view_menu(window).actions()
    assert [a.isChecked() for a in actions[:5]] == [False, True, False, False, False]
    actions[2].trigger()
    actions[4].trigger()
    assert window.calls == [("tile_size", 512), ("tile_size", "None")]


def test_browse_mode_submenu_wires_grid_and_list(window):
    menu = _view_menu(window)
    mode = menu.actions()[6].menu()
    grid, list_ = mode.actions()
    assert window._mode_action_grid is grid  # noqa: SLF001
    assert window._mode_action_list is list_  # noqa: SLF001
    assert grid.isChecked() and not list_.isChecked()
    list_.trigger()
    grid.trigger()
    assert window.calls == [("browse_mode", "list"), ("browse_mode", "grid")]


@pytest.mark.parametrize(("padding", "checked"), [
    (0, [True, False, False]), (8, [False, True, False]),
    (16, [False, False, True]), (5, [False, False, False]),
])
def test_density_submenu_checks_current_padding(qapp, padding, checked):
    win = _StubMainWindow(tile_padding=padding)
    try:
        density = _view_menu(win).actions()[8].menu()
        assert [a.isChecked() for a in density.actions()] == checked
        density.actions()[2].trigger()
        assert win.calls == [("tile_padding", 16)]
    finally:
        win.deleteLater()
