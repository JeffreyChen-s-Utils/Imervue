"""Tests for the multi-document tab strip in PaintWorkspace."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PaintCanvas, PointerEvent
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


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_workspace_starts_with_one_tab(workspace):
    assert workspace.tab_count() == 1
    assert isinstance(workspace.canvas(), PaintCanvas)


def test_initial_tab_has_blank_document(workspace):
    document = workspace.canvas().document()
    assert document.shape is not None
    assert document.layer_count >= 1


# ---------------------------------------------------------------------------
# new_tab
# ---------------------------------------------------------------------------


def test_new_tab_grows_count_and_switches(workspace):
    first = workspace.canvas()
    workspace.new_tab()
    assert workspace.tab_count() == 2
    # After ``new_tab`` the new canvas is active.
    assert workspace.canvas() is not first


def test_each_tab_has_independent_document(workspace):
    first = workspace.canvas()
    workspace.new_tab()
    second = workspace.canvas()
    # Mutating one document must not affect the other.
    second.document().add_layer()
    assert first.document().layer_count != second.document().layer_count


def test_new_tab_canvas_uses_workspace_dispatcher(workspace):
    workspace.new_tab()
    new_canvas = workspace.canvas()
    # The dispatcher attached to the new canvas is the workspace's
    # shared one — so brush events keep flowing without re-wiring.
    assert new_canvas._dispatcher is workspace._dispatcher  # noqa: SLF001


# ---------------------------------------------------------------------------
# Tab switching
# ---------------------------------------------------------------------------


def test_switch_tab_reassigns_active_canvas(workspace):
    first = workspace.canvas()
    workspace.new_tab()
    second = workspace.canvas()
    # Switch back to the first tab via the QTabWidget index.
    workspace._tabs.setCurrentIndex(0)  # noqa: SLF001
    assert workspace.canvas() is first
    workspace._tabs.setCurrentIndex(1)  # noqa: SLF001
    assert workspace.canvas() is second


def test_switch_tab_rebinds_layer_dock(workspace):
    workspace.new_tab()
    second_doc = workspace.canvas().document()
    workspace._tabs.setCurrentIndex(0)  # noqa: SLF001
    first_doc = workspace.canvas().document()
    assert workspace._layer_dock._document is first_doc  # noqa: SLF001
    workspace._tabs.setCurrentIndex(1)  # noqa: SLF001
    assert workspace._layer_dock._document is second_doc  # noqa: SLF001


def test_dispatcher_routes_to_active_tabs_canvas(workspace):
    """A brush press routed through the workspace dispatcher must
    paint into the active tab's canvas — not the previous one."""
    first = workspace.canvas()
    workspace.new_tab()
    second = workspace.canvas()
    # Snapshot both.
    first_before = first.document().layer_at(0).image.copy()
    second_before = second.document().layer_at(0).image.copy()
    workspace.state().set_foreground((255, 0, 0))
    evt = PointerEvent(
        phase="press", x=20, y=20, button=1, modifiers=0, pressure=1.0,
    )
    workspace._dispatcher(evt)  # noqa: SLF001
    # Active tab (second) must show a change; first tab must not.
    assert (second.document().layer_at(0).image != second_before).any()
    assert np.array_equal(first.document().layer_at(0).image, first_before)


# ---------------------------------------------------------------------------
# close_tab
# ---------------------------------------------------------------------------


def test_close_tab_drops_count(workspace):
    workspace.new_tab()
    assert workspace.tab_count() == 2
    workspace.close_tab(1)
    assert workspace.tab_count() == 1


def test_close_last_tab_refused(workspace):
    """The workspace must always keep at least one paintable canvas."""
    assert workspace.tab_count() == 1
    closed = workspace.close_tab(0)
    assert closed is False
    assert workspace.tab_count() == 1


def test_close_tab_out_of_range_returns_false(workspace):
    assert workspace.close_tab(99) is False


def test_close_tab_via_x_button(workspace):
    """The QTabWidget's tabCloseRequested signal must route through
    the same close_tab path so the limit-protection works."""
    workspace.new_tab()
    workspace._on_tab_close_requested(1)  # noqa: SLF001
    assert workspace.tab_count() == 1
    # Refuses to close the only remaining tab.
    workspace._on_tab_close_requested(0)  # noqa: SLF001
    assert workspace.tab_count() == 1


# ---------------------------------------------------------------------------
# File-menu bridge
# ---------------------------------------------------------------------------


def test_file_menu_new_tab_action_grows_count(workspace):
    bridge = workspace._file_menu_bridge   # noqa: SLF001
    bridge.new_tab()
    assert workspace.tab_count() == 2


def test_file_menu_close_tab_action_drops_count(workspace):
    bridge = workspace._file_menu_bridge   # noqa: SLF001
    workspace.new_tab()
    bridge.close_active_tab()
    assert workspace.tab_count() == 1
