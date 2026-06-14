"""Tests for the brush-kind cycle shortcut."""
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


def test_cycle_forward_advances_to_next_kind(workspace):
    kinds = list(ts.BRUSH_KINDS)
    workspace.state().set_brush(kind=kinds[0])
    new_kind = workspace.cycle_brush_kind(1)
    assert new_kind == kinds[1]
    assert workspace.state().brush.kind == kinds[1]


def test_cycle_backward_returns_previous_kind(workspace):
    kinds = list(ts.BRUSH_KINDS)
    workspace.state().set_brush(kind=kinds[1])
    new_kind = workspace.cycle_brush_kind(-1)
    assert new_kind == kinds[0]


def test_cycle_wraps_around_at_end(workspace):
    """Forward from the last kind returns to the first — pure
    modulo cycle, no clamping that would surprise the user."""
    kinds = list(ts.BRUSH_KINDS)
    workspace.state().set_brush(kind=kinds[-1])
    assert workspace.cycle_brush_kind(1) == kinds[0]


def test_cycle_emits_toast(workspace, monkeypatch):
    received = []
    monkeypatch.setattr(
        workspace.toast, "info",
        lambda text, **k: received.append(text),
    )
    workspace.cycle_brush_kind(1)
    assert received
    assert any(c.isalpha() for c in received[0])
