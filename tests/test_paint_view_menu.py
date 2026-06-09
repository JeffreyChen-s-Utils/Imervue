"""Tests for the View menu and its toggle bridge."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_menu_bar import menu_for
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.view_menu import _ViewMenuBridge
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Menu population
# ---------------------------------------------------------------------------


def test_view_menu_has_documented_actions(qapp):
    ws = PaintWorkspace()
    try:
        view_menu = menu_for(ws, "view")
        # 6 toggles + Hide All Docks (Tab) + 1 sep + 2 rotation = 10.
        assert len(view_menu.actions()) == 10
    finally:
        ws.deleteLater()


def test_view_menu_actions_have_translated_labels(qapp):
    ws = PaintWorkspace()
    try:
        view_menu = menu_for(ws, "view")
        labels = [a.text() for a in view_menu.actions() if not a.isSeparator()]
        for label in labels:
            assert not label.startswith("paint_view_"), label
    finally:
        ws.deleteLater()


def test_view_menu_toggles_are_checkable(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        for key in (
            "paint_view_pixel_grid", "paint_view_snap_pixel",
            "paint_view_onion_skin", "paint_view_quick_mask",
            "paint_view_bleed_guides",
        ):
            action = bridge._actions[key]   # noqa: SLF001
            assert action.isCheckable(), key
    finally:
        ws.deleteLater()


def test_view_rotation_actions_are_not_checkable(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        for key in ("paint_view_rotate_ccw", "paint_view_reset_rotation"):
            assert not bridge._actions[key].isCheckable(), key  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_holds_bridge_reference(qapp):
    ws = PaintWorkspace()
    try:
        assert isinstance(ws._view_menu_bridge, _ViewMenuBridge)  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Toggle behaviour
# ---------------------------------------------------------------------------


def test_toggle_snap_to_pixel_writes_state(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.toggle_snap_to_pixel(True)
        assert ws.state().snap_to_pixel is True
        bridge.toggle_snap_to_pixel(False)
        assert ws.state().snap_to_pixel is False
    finally:
        ws.deleteLater()


def test_toggle_quick_mask_writes_state(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.toggle_quick_mask(True)
        assert ws.state().quick_mask_active is True
        bridge.toggle_quick_mask(False)
        assert ws.state().quick_mask_active is False
    finally:
        ws.deleteLater()


def test_toggle_pixel_grid_flips_workspace_flag(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.toggle_pixel_grid(True)
        assert ws._pixel_grid_visible is True   # noqa: SLF001
        bridge.toggle_pixel_grid(False)
        assert ws._pixel_grid_visible is False   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_toggle_onion_skin_flips_workspace_flag(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.toggle_onion_skin(True)
        assert ws._onion_skin_visible is True   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_toggle_bleed_guides_flips_workspace_flag(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.toggle_bleed_guides(True)
        assert ws._bleed_guides_visible is True   # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Initial-state accessors
# ---------------------------------------------------------------------------


def test_initial_state_reads_from_tool_state(qapp):
    """Snap-to-pixel and quick-mask survive across workspace
    instances via the persisted ToolState."""
    state = ts.load_tool_state()
    state.snap_to_pixel = True
    state.quick_mask_active = True
    ws = PaintWorkspace(state=state)
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        assert bridge.snap_to_pixel_active() is True
        assert bridge.quick_mask_active() is True
    finally:
        ws.deleteLater()


def test_initial_state_default_when_unset(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        assert bridge.pixel_grid_active() is False
        assert bridge.onion_skin_active() is False
        assert bridge.bleed_guides_active() is False
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Canvas rotation actions short-circuit gracefully
# ---------------------------------------------------------------------------


def test_rotate_ccw_does_not_crash_without_canvas_support(qapp):
    """Pre-21g canvas may not implement set_rotation_around_centre.
    The bridge logs and continues rather than propagating
    AttributeError into the menu action's slot."""
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        # Should not raise.
        bridge.rotate_canvas_ccw()
        bridge.reset_canvas_rotation()
    finally:
        ws.deleteLater()


def test_pixel_grid_label_gains_zoom_in_suffix_when_dormant(qapp):
    """Toggling Pixel Grid below the zoom threshold leaves the toast
    a few seconds after which it disappears. The menu action's
    label keeps the "(zoom in)" cue for as long as the condition
    holds — without it the user only sees a checkmark and assumes
    the toggle is broken."""
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        action = bridge._actions["paint_view_pixel_grid"]   # noqa: SLF001
        # Force a low zoom — well below the 4× threshold.
        ws.canvas()._zoom = 1.0   # noqa: SLF001
        bridge.toggle_pixel_grid(True)
        assert "(zoom in" in action.text()
        # Bumping zoom past the threshold drops the suffix.
        ws.canvas()._zoom = 8.0   # noqa: SLF001
        bridge.refresh_pixel_grid_label()
        assert "(zoom in" not in action.text()
        # Disabling the toggle also clears the suffix.
        ws.canvas()._zoom = 1.0   # noqa: SLF001
        bridge.toggle_pixel_grid(False)
        assert "(zoom in" not in action.text()
    finally:
        ws.deleteLater()
