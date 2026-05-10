"""Tests for the paint workspace's "+" new-tab corner button — Phase 35a.

The tab strip used to expose only ``Ctrl+T`` as the "new tab" affordance.
Mounting a corner-widget ``+`` button gives the same action a hover-
discoverable surface and surfaces the keyboard hint via tooltip.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def test_new_tab_corner_widget_is_present(qapp):
    ws = PaintWorkspace()
    try:
        corner = ws._tabs.cornerWidget(Qt.Corner.TopRightCorner)   # noqa: SLF001
        assert isinstance(corner, QToolButton)
        assert corner.text() == "+"
    finally:
        ws.deleteLater()


def test_new_tab_button_tooltip_includes_shortcut(qapp):
    ws = PaintWorkspace()
    try:
        corner = ws._tabs.cornerWidget(Qt.Corner.TopRightCorner)   # noqa: SLF001
        assert "Ctrl+T" in corner.toolTip()
    finally:
        ws.deleteLater()


def test_clicking_new_tab_button_adds_tab(qapp):
    ws = PaintWorkspace()
    try:
        before = ws._tabs.count()   # noqa: SLF001
        corner = ws._tabs.cornerWidget(Qt.Corner.TopRightCorner)   # noqa: SLF001
        corner.click()
        assert ws._tabs.count() == before + 1   # noqa: SLF001
    finally:
        ws.deleteLater()
