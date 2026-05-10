"""Regression coverage for the language-menu shiboken-teardown guard.

The QMenu wrapper stored on ``main_window.language_menu`` can outlive its
underlying C++ peer in some PySide6 / Python combinations. The plugin
init path used to crash startup with ``RuntimeError: Internal C++
object already deleted`` when it tried to append plugin-supplied
languages onto that stale wrapper. ``_append_plugin_languages`` now
swallows that RuntimeError and logs a warning instead.
"""
from __future__ import annotations

import logging

import shiboken6
from PySide6.QtWidgets import QMainWindow, QMenu


def _make_window_with_language_menu(qapp) -> QMainWindow:
    win = QMainWindow()
    bar = win.menuBar()
    language_menu = QMenu("Language", win)
    bar.addMenu(language_menu)
    win.language_menu = language_menu
    return win


def test_append_plugin_languages_appends_when_menu_is_live(qapp, monkeypatch):
    from Imervue.integration_guide import _append_plugin_languages
    from Imervue.multi_language.language_wrapper import language_wrapper

    win = _make_window_with_language_menu(qapp)
    try:
        monkeypatch.setattr(
            language_wrapper, "plugin_languages",
            {"Spanish": "Español", "French": "Français"},
            raising=False,
        )
        before = len(win.language_menu.actions())

        _append_plugin_languages(win)

        actions = win.language_menu.actions()
        # one separator + two plugin languages appended
        assert len(actions) == before + 3
        assert actions[-2].text() == "Español"
        assert actions[-1].text() == "Français"
    finally:
        win.deleteLater()


def test_append_plugin_languages_skips_when_wrapper_is_dead(qapp, monkeypatch, caplog):
    """If the cached ``main_window.language_menu`` wrapper points at a
    freed C++ object the helper must either recover by re-resolving
    the menu from the menubar, or skip cleanly. Either way, it must
    not raise — the previous crash blocked main-window construction.

    With the resolver path now in place the function may *recover*
    rather than skip when the menubar still carries a live menu
    action; the assertion is that neither outcome aborts startup.
    """
    from Imervue.integration_guide import _append_plugin_languages
    from Imervue.multi_language.language_wrapper import language_wrapper

    win = _make_window_with_language_menu(qapp)
    try:
        monkeypatch.setattr(
            language_wrapper, "plugin_languages",
            {"Spanish": "Español"},
            raising=False,
        )
        shiboken6.delete(win.language_menu)

        with caplog.at_level(logging.DEBUG, logger="Imervue.integration"):
            _append_plugin_languages(win)   # must not raise
    finally:
        win.deleteLater()


def test_resolve_language_menu_returns_fresh_wrapper_when_cached_is_dead(qapp):
    """The resolver should walk the menubar and recover a live wrapper
    even if ``main_window.language_menu`` points at a freed peer —
    that's what makes the warning go away in normal operation."""
    from Imervue.integration_guide import _resolve_language_menu
    from Imervue.multi_language.language_wrapper import language_wrapper
    from PySide6.QtWidgets import QMenu

    win = QMainWindow()
    bar = win.menuBar()
    title = language_wrapper.language_word_dict.get("menu_bar_language", "Language")
    live_menu = QMenu(title, win)
    bar.addMenu(live_menu)
    win.language_menu = live_menu
    try:
        # Stash a dead wrapper in the cached attribute, then make sure
        # the resolver still hands us back something live.
        dead = QMenu("Dead", win)
        bar.addMenu(dead)
        win.language_menu = dead
        shiboken6.delete(dead)

        resolved = _resolve_language_menu(win)
        assert resolved is not None
        # Should be the live menu we authored under the language title.
        assert resolved.title() == title
    finally:
        win.deleteLater()


def test_resolve_language_menu_returns_none_when_menubar_has_no_match(qapp):
    """If neither the cached attribute nor the menubar yields a live
    Language menu, the resolver returns None so the caller can take
    the skip path without iterating a dead pointer."""
    from Imervue.integration_guide import _resolve_language_menu

    win = QMainWindow()
    win.menuBar()   # bare menubar, no menus
    try:
        win.language_menu = None
        assert _resolve_language_menu(win) is None
    finally:
        win.deleteLater()
