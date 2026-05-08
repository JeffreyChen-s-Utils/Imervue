"""Tests for the Ctrl+Tab / Ctrl+Shift+Tab paint tab cycle."""
from __future__ import annotations

import pytest

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


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_cycle_forward_advances_tab(workspace):
    workspace.new_tab()
    workspace._tabs.setCurrentIndex(0)  # noqa: SLF001
    new_idx = workspace.cycle_active_tab(+1)
    assert new_idx == 1
    assert workspace._tabs.currentIndex() == 1  # noqa: SLF001


def test_cycle_backward_wraps_to_last(workspace):
    workspace.new_tab()
    workspace._tabs.setCurrentIndex(0)  # noqa: SLF001
    new_idx = workspace.cycle_active_tab(-1)
    assert new_idx == 1


def test_cycle_with_single_tab_stays_put(workspace):
    """Cycling a single-tab workspace is a no-op rather than a
    crash — wrap-around math against a 1-element bar still
    converges to index 0."""
    assert workspace._tabs.count() == 1  # noqa: SLF001
    new_idx = workspace.cycle_active_tab(+1)
    assert new_idx == 0
