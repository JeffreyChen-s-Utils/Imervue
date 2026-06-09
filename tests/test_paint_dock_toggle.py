"""Tests for the workspace-wide hide / show docks toggle."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_toggle_all_docks_first_call_hides_visible_docks(workspace):
    """Snapshot which docks were visible, then hide every one of
    them. Subsequent isVisible reads False (Qt parent is unshown,
    but ``_docks_collapsed`` is the source of truth)."""
    # Capture pre-toggle visibility from the dock widget itself
    # (Qt's isVisible is False off-screen, but isHidden is True only
    # when explicitly hidden).
    docks = (
        workspace._dock_clusters["drawing"]   # noqa: SLF001
        + workspace._dock_clusters["canvas"]
        + workspace._dock_clusters["library"]
    )
    pre_hidden = {dock: dock.isHidden() for dock in docks}
    workspace.toggle_all_docks()
    # Every dock previously *not* hidden should now be hidden.
    for dock, was_hidden in pre_hidden.items():
        if not was_hidden:
            assert dock.isHidden(), f"{dock} should be hidden"
    assert workspace._docks_collapsed is not None  # noqa: SLF001


def test_toggle_all_docks_second_call_restores(workspace):
    """Calling the toggle a second time restores the captured
    visibility set, even when the widget tree is off-screen."""
    docks = (
        workspace._dock_clusters["drawing"]   # noqa: SLF001
        + workspace._dock_clusters["canvas"]
        + workspace._dock_clusters["library"]
    )
    pre_hidden = {dock: dock.isHidden() for dock in docks}
    workspace.toggle_all_docks()
    workspace.toggle_all_docks()
    assert workspace._docks_collapsed is None  # noqa: SLF001
    for dock, was_hidden in pre_hidden.items():
        # Only docks that started visible should re-appear.
        assert dock.isHidden() == was_hidden


def test_toggle_keeps_user_hidden_dock_hidden(workspace):
    """A dock the user manually hid before toggling stays hidden
    after the round-trip — Photoshop convention."""
    color = workspace._color_dock   # noqa: SLF001
    color.setVisible(False)
    workspace.toggle_all_docks()  # collapse all
    workspace.toggle_all_docks()  # restore
    assert color.isHidden() is True


def test_view_menu_includes_toggle_action(workspace):
    """Verify the View menu surfaces the bound Tab shortcut so the
    keystroke actually reaches the workspace toggle."""
    bridge = workspace._view_menu_bridge   # noqa: SLF001
    actions = bridge._actions   # noqa: SLF001
    assert "paint_view_toggle_all_docks" in actions
    action = actions["paint_view_toggle_all_docks"]
    assert action.shortcut().toString() == "Tab"
