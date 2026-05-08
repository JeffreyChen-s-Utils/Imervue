"""Tests for the digit-key brush opacity shortcut."""
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


@pytest.mark.parametrize("digit,expected", [
    (1, 0.10),
    (2, 0.20),
    (5, 0.50),
    (9, 0.90),
    (0, 1.00),
])
def test_digit_maps_to_documented_opacity(workspace, digit, expected):
    actual = workspace.set_brush_opacity_from_digit(digit)
    assert actual == pytest.approx(expected)
    assert workspace.state().brush.opacity == pytest.approx(expected)


def test_digit_emits_confirmation_toast(workspace, monkeypatch):
    received = []
    monkeypatch.setattr(
        workspace.toast, "info",
        lambda text, **k: received.append(text),
    )
    workspace.set_brush_opacity_from_digit(7)
    assert received
    assert "70" in received[0]


def test_out_of_range_digit_uses_modulo(workspace):
    """Anything outside 0-9 maps via modulo so a stray ``QShortcut``
    overshoot doesn't crash. ``11`` → digit 1 → 10 %."""
    assert workspace.set_brush_opacity_from_digit(11) == pytest.approx(0.1)
