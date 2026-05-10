"""Tests for the main image viewer's menubar tooltipsVisible flag — phase 36i.

QMenu hides per-action tooltips by default. ``_enable_tooltips_on_all_menus``
walks the bar once so every action's setToolTip() actually surfaces on
hover, without each builder having to remember to flip the flag.
"""
from __future__ import annotations

import shiboken6
from PySide6.QtWidgets import QMainWindow, QMenu


def _make_window_with_menus(qapp) -> QMainWindow:
    win = QMainWindow()
    bar = win.menuBar()
    file_menu = QMenu("File", win)
    bar.addMenu(file_menu)
    edit_menu = QMenu("Edit", win)
    bar.addMenu(edit_menu)
    submenu = QMenu("Recent", win)
    file_menu.addMenu(submenu)
    return win


def test_helper_enables_tooltips_on_top_level_and_submenus(qapp, monkeypatch):
    """The helper must reach every menu in the bar plus any nested
    submenus, since recent / language / submenu chains carry their
    own action surfaces."""
    from Imervue.Imervue_main_window import ImervueMainWindow

    win = _make_window_with_menus(qapp)
    try:
        bound_helper = ImervueMainWindow._enable_tooltips_on_all_menus
        bound_helper(win)
        bar = win.menuBar()
        for action in bar.actions():
            menu = action.menu()
            if menu is None:
                continue
            assert menu.toolTipsVisible(), f"{action.text()!r} missing flag"
            for child_action in menu.actions():
                child_menu = child_action.menu()
                if child_menu is not None:
                    assert child_menu.toolTipsVisible(), (
                        f"submenu {child_action.text()!r} missing flag"
                    )
    finally:
        win.deleteLater()


def test_helper_is_safe_when_no_menubar(qapp, monkeypatch):
    """A bare QMainWindow with no constructed menus must not crash —
    the helper should bail out cleanly so it can be called early in
    construction without ordering hazards."""
    from Imervue.Imervue_main_window import ImervueMainWindow

    win = QMainWindow()
    try:
        bound_helper = ImervueMainWindow._enable_tooltips_on_all_menus
        bound_helper(win)   # must not raise even on an empty bar
    finally:
        win.deleteLater()


def test_helper_skips_deleted_qmenu_wrappers(qapp):
    """If a menubar-reachable QMenu's C++ side has already been freed
    (a shiboken teardown hazard observed in the wild on PySide6), the
    walker must skip the dangling wrapper and still flip the flag on
    the surviving menus rather than aborting window construction."""
    from Imervue.Imervue_main_window import ImervueMainWindow

    win = QMainWindow()
    try:
        bar = win.menuBar()
        live_menu = QMenu("Live", win)
        bar.addMenu(live_menu)
        dead_menu = QMenu("Dead", win)
        bar.addMenu(dead_menu)
        # Force shiboken to treat the wrapper as pointing at a freed
        # C++ object — this is the exact failure mode reported in the
        # field crash trace.
        shiboken6.delete(dead_menu)

        ImervueMainWindow._enable_tooltips_on_all_menus(win)

        assert live_menu.toolTipsVisible(), "live menu should still be flipped"
    finally:
        win.deleteLater()


def test_safe_submenus_of_skips_deleted_actions(qapp):
    """Direct unit coverage for the submenu-listing helper so we have
    a focused regression test for the guard, independent of the
    public walker."""
    from Imervue.Imervue_main_window import _safe_submenus_of

    win = QMainWindow()
    try:
        bar = win.menuBar()
        live_menu = QMenu("Live", win)
        bar.addMenu(live_menu)
        dead_menu = QMenu("Dead", win)
        bar.addMenu(dead_menu)
        shiboken6.delete(dead_menu)

        submenus = _safe_submenus_of(bar)

        assert live_menu in submenus
        assert all(shiboken6.isValid(m) for m in submenus)
    finally:
        win.deleteLater()
