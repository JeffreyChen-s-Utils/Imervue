"""Tests for the Paint workspace menu bar structure."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_menu_bar import (
    MENU_KEYS,
    build_paint_menu_bar,
    menu_for,
)
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


def test_menu_keys_documented_set():
    """Drift detector — adding a menu without updating tests should
    fail loudly here rather than silently shipping a half-translated
    UI."""
    keys = {key for key, _label_key in MENU_KEYS}
    assert keys == {
        "file", "edit", "layer", "view",
        "tools", "filter", "settings", "window",
    }


def test_menu_keys_all_have_translation_keys():
    for key, label_key in MENU_KEYS:
        assert label_key.startswith("paint_menu_"), key


# ---------------------------------------------------------------------------
# Construction via PaintWorkspace
# ---------------------------------------------------------------------------


def test_workspace_menu_bar_has_eight_top_level_menus(qapp):
    ws = PaintWorkspace()
    try:
        bar = ws.menuBar()
        # menuBar().actions() returns one QAction per top-level menu.
        assert len(bar.actions()) == len(MENU_KEYS)
    finally:
        ws.deleteLater()


def test_workspace_stashes_menus_under_documented_keys(qapp):
    ws = PaintWorkspace()
    try:
        for key, _label_key in MENU_KEYS:
            menu = menu_for(ws, key)
            assert menu is not None
            assert getattr(ws, f"_{key}_menu") is menu
    finally:
        ws.deleteLater()


def test_filter_menu_keeps_existing_actions(qapp):
    """Restructure mustn't lose the populated Filter menu entries
    that filter_menu.build_filter_menu produced."""
    ws = PaintWorkspace()
    try:
        filter_menu = menu_for(ws, "filter")
        assert filter_menu.actions(), "Filter menu lost its actions in 21a"
    finally:
        ws.deleteLater()


def test_other_menus_start_empty(qapp):
    """21b–21g hang the actions; 21a creates them empty so a test
    that expects "did 21b populate File?" can assert on count."""
    ws = PaintWorkspace()
    try:
        for key in ("edit", "layer", "view", "tools", "settings", "window"):
            menu = menu_for(ws, key)
            assert menu.actions() == []
    finally:
        ws.deleteLater()


def test_menu_for_unknown_key_raises(qapp):
    ws = PaintWorkspace()
    try:
        with pytest.raises(KeyError, match="unknown menu key"):
            menu_for(ws, "preferences")
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Direct build_paint_menu_bar — without the workspace fixture
# ---------------------------------------------------------------------------


def test_build_returns_menu_bar_with_documented_count(qapp):
    """The factory takes any QMainWindow-shaped owner; calling it
    directly returns a QMenuBar with the expected number of menus."""
    from PySide6.QtWidgets import QMainWindow
    owner = QMainWindow()
    try:
        bar = build_paint_menu_bar(owner)
        assert len(bar.actions()) == len(MENU_KEYS)
    finally:
        owner.deleteLater()
