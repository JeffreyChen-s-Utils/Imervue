"""Tests for the Modify/Paint tab Left/Right arrow routing decision.

``tab_arrow_action`` is pure — it maps ``(tab_index, key)`` to an image-nav
action or ``None`` — so it is tested directly without the GL-backed main
window. Fake key codes stand in for ``Qt.Key_Left`` / ``Qt.Key_Right``.
"""
from __future__ import annotations

from Imervue.gui.main_tab_nav import (
    MODIFY_TAB_INDEX,
    PAINT_TAB_INDEX,
    tab_arrow_action,
)

_LEFT = 1000
_RIGHT = 1001
_OTHER = 1002


def test_left_on_modify_tab_pages_previous():
    assert tab_arrow_action(MODIFY_TAB_INDEX, _LEFT, _LEFT, _RIGHT) == ("modify", -1)


def test_right_on_modify_tab_pages_next():
    assert tab_arrow_action(MODIFY_TAB_INDEX, _RIGHT, _LEFT, _RIGHT) == ("modify", 1)


def test_left_on_paint_tab_pages_previous():
    assert tab_arrow_action(PAINT_TAB_INDEX, _LEFT, _LEFT, _RIGHT) == ("paint", -1)


def test_right_on_paint_tab_pages_next():
    assert tab_arrow_action(PAINT_TAB_INDEX, _RIGHT, _LEFT, _RIGHT) == ("paint", 1)


def test_browse_tab_arrows_fall_through():
    # Index 0 (browse) keeps the default tab-bar behaviour → no action.
    assert tab_arrow_action(0, _LEFT, _LEFT, _RIGHT) is None
    assert tab_arrow_action(0, _RIGHT, _LEFT, _RIGHT) is None


def test_other_tab_arrows_fall_through():
    # A tab past Paint (e.g. Puppet at 3) is not an image-nav tab.
    assert tab_arrow_action(3, _RIGHT, _LEFT, _RIGHT) is None


def test_non_arrow_key_falls_through_even_on_nav_tab():
    assert tab_arrow_action(MODIFY_TAB_INDEX, _OTHER, _LEFT, _RIGHT) is None
    assert tab_arrow_action(PAINT_TAB_INDEX, _OTHER, _LEFT, _RIGHT) is None
