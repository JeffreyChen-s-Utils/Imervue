"""Tests for the 21g dock integrations.

* SwatchPanel added as a workspace dock with a Window-menu toggle.
* Color-wheel widget exposes the unit-coordinate helpers from
  color_wheel.py.
* Workspace owns a SizeHudState for the brush-size HUD overlay.
"""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_menu_bar import menu_for
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.swatch_panel import SwatchPanel
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Swatch dock
# ---------------------------------------------------------------------------


def test_workspace_owns_swatch_dock(qapp):
    ws = PaintWorkspace()
    try:
        assert isinstance(ws._swatch_dock, SwatchPanel)  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_now_has_eight_docks(qapp):
    """Was seven before 24d — adding the reference dock makes eight."""
    from PySide6.QtWidgets import QDockWidget
    ws = PaintWorkspace()
    try:
        docks = ws.findChildren(QDockWidget)
        assert len(docks) == 8
    finally:
        ws.deleteLater()


def test_swatch_dock_click_updates_foreground(qapp):
    ws = PaintWorkspace()
    try:
        # Simulate the swatch panel emitting a colour pick.
        ws._swatch_dock.color_chosen.emit(123, 45, 67)  # noqa: SLF001
        assert ws.state().foreground == (123, 45, 67)
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Window menu
# ---------------------------------------------------------------------------


def test_window_menu_populates_one_entry_per_dock(qapp):
    ws = PaintWorkspace()
    try:
        window_menu = menu_for(ws, "window")
        # Eight docks → eight Window-menu entries (24d added Reference).
        assert len(window_menu.actions()) == 8
    finally:
        ws.deleteLater()


def test_window_menu_actions_are_checkable(qapp):
    ws = PaintWorkspace()
    try:
        window_menu = menu_for(ws, "window")
        for action in window_menu.actions():
            assert action.isCheckable(), action.text()
    finally:
        ws.deleteLater()


def test_window_menu_toggle_hides_dock(qapp):
    """Hide the dock externally; the menu action must follow."""
    ws = PaintWorkspace()
    try:
        action = ws._window_dock_actions["paint_dock_swatches"]   # noqa: SLF001
        ws._swatch_dock.setVisible(False)  # noqa: SLF001
        # The visibilityChanged signal updates the action's check
        # state to mirror the dock.
        assert not action.isChecked()
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Brush-size HUD state
# ---------------------------------------------------------------------------


def test_workspace_owns_size_hud_state(qapp):
    from Imervue.paint.size_hud import SizeHudState
    ws = PaintWorkspace()
    try:
        assert isinstance(ws._size_hud, SizeHudState)  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Color wheel widget
# ---------------------------------------------------------------------------


def test_color_wheel_widget_initial_color_round_trips(qapp):
    from Imervue.paint.color_wheel_widget import ColorWheelWidget
    widget = ColorWheelWidget(initial_rgb=(255, 0, 0))
    try:
        # The HSV round-trip is lossy at saturation/value boundaries,
        # but pure red must round back to itself.
        r, g, b = widget.color()
        assert (r, g, b) == (255, 0, 0)
    finally:
        widget.deleteLater()


def test_color_wheel_widget_set_color(qapp):
    from Imervue.paint.color_wheel_widget import ColorWheelWidget
    widget = ColorWheelWidget()
    try:
        widget.set_color((0, 200, 0))
        r, g, b = widget.color()
        assert g == 200
        assert r == 0 and b == 0
    finally:
        widget.deleteLater()


def test_color_wheel_widget_unit_round_trip(qapp):
    """The widget's coordinate helpers compose to identity."""
    from Imervue.paint.color_wheel_widget import ColorWheelWidget
    widget = ColorWheelWidget()
    widget.resize(220, 220)
    try:
        # We can't rely on the exact widget centre without showing
        # the widget, but the round-trip property must hold.
        unit = (0.5, -0.3)
        screen = widget._from_unit(unit)  # noqa: SLF001
        recovered = widget._to_unit(screen)  # noqa: SLF001
        assert recovered == pytest.approx(unit, abs=1e-6)
    finally:
        widget.deleteLater()
