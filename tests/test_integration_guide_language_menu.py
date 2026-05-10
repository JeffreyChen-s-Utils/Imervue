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
    """If the C++ QMenu has been freed, the helper must skip silently
    rather than abort plugin init — the previous crash blocked the
    main window from finishing construction."""
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

        with caplog.at_level(logging.WARNING, logger="Imervue.integration"):
            _append_plugin_languages(win)  # must not raise

        assert any(
            "language_menu" in rec.message and "deleted" in rec.message
            for rec in caplog.records
        )
    finally:
        win.deleteLater()
