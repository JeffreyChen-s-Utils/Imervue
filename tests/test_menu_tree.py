"""Menu walking without ``QAction.menu()`` (``Imervue/gui/menu_tree.py``)."""
from __future__ import annotations

import gc

import shiboken6
from PySide6.QtWidgets import QMainWindow, QMenu

from Imervue.gui.menu_tree import iter_menu_actions, submenu_index, submenu_of


def _window():
    win = QMainWindow()
    bar = win.menuBar()
    file_menu = bar.addMenu("&File")
    file_menu.addAction("Open")
    file_menu.addSeparator()
    recent = file_menu.addMenu("Recent")
    recent.addAction("a.png")
    # a menu parented to the window and added by object, as the paint tab does
    edit = QMenu("Edit", win)
    bar.addMenu(edit)
    edit.addAction("Undo")
    bar.addAction("Modify")          # a plain action directly on the bar
    return win, file_menu, recent, edit


def test_iter_menu_actions_walks_in_order_with_paths(qapp):
    win, *_ = _window()
    try:
        walked = [(path, a.text()) for path, a in iter_menu_actions(win.menuBar(), submenu_index(win))]
        assert walked == [
            (("File",), "Open"),
            (("File", "Recent"), "a.png"),
            (("Edit",), "Undo"),
            ((), "Modify"),
        ]
    finally:
        win.deleteLater()


def test_index_scoped_to_the_bar_misses_menus_parented_elsewhere(qapp):
    win, _file_menu, _recent, edit = _window()
    try:
        index = submenu_index(win.menuBar())
        assert submenu_of(edit.menuAction(), index) is None
        assert submenu_of(edit.menuAction(), submenu_index(win)) is edit
    finally:
        win.deleteLater()


def test_submenu_of_plain_action_is_none(qapp):
    win, file_menu, *_ = _window()
    try:
        open_action = file_menu.actions()[0]
        assert submenu_of(open_action, submenu_index(win)) is None
    finally:
        win.deleteLater()


def test_walk_keeps_cached_wrappers_valid(qapp):
    win, file_menu, recent, edit = _window()
    try:
        def walk():
            return list(iter_menu_actions(win.menuBar(), submenu_index(win)))

        walk()
        gc.collect()
        for menu in (file_menu, recent, edit):
            assert shiboken6.isValid(menu)
            menu.addSeparator()      # would raise on an invalidated wrapper
    finally:
        win.deleteLater()


def test_empty_bar_yields_nothing(qapp):
    win = QMainWindow()
    try:
        assert list(iter_menu_actions(win.menuBar(), submenu_index(win))) == []
    finally:
        win.deleteLater()
