"""Tests for the active-layer cycle hotkey."""
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


def test_cycle_up_advances_active_layer_index(workspace):
    document = workspace.canvas().document()
    document.add_layer(name="Highlights")
    document.add_layer(name="Sketch")
    document.set_active_layer(0)
    new_idx = workspace.cycle_active_layer(+1)
    assert new_idx == 1
    assert document.active_layer_index() == 1


def test_cycle_down_steps_back(workspace):
    document = workspace.canvas().document()
    document.add_layer(name="Highlights")
    document.add_layer(name="Sketch")
    document.set_active_layer(2)
    new_idx = workspace.cycle_active_layer(-1)
    assert new_idx == 1


def test_cycle_clamps_at_bottom(workspace):
    """Stepping past the bottom must clamp, not wrap — wrapping
    would loop the user back to the top with no warning."""
    document = workspace.canvas().document()
    document.set_active_layer(0)
    new_idx = workspace.cycle_active_layer(-1)
    assert new_idx == 0


def test_cycle_clamps_at_top(workspace):
    document = workspace.canvas().document()
    document.add_layer(name="Highlights")
    document.set_active_layer(1)
    new_idx = workspace.cycle_active_layer(+1)
    assert new_idx == 1


def test_cycle_emits_toast_with_new_layer_name(workspace, monkeypatch):
    received = []
    monkeypatch.setattr(
        workspace.toast, "info",
        lambda text, **k: received.append(text),
    )
    document = workspace.canvas().document()
    document.add_layer(name="Highlights")
    document.set_active_layer(0)
    workspace.cycle_active_layer(+1)
    assert received
    assert "Highlight" in received[0]
