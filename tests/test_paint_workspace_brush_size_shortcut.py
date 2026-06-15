"""Tests for the ``[`` / ``]`` brush-size shortcut and its helper.

Phase 34e wires Photoshop / -style bracket-key brush sizing.
``step_brush_size`` clamps to the documented range, no-ops at the
boundary, and refreshes the status line so the change is visible.
"""
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


def test_step_brush_size_increment(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_brush(size=12)   # noqa: SLF001
        new = ws.step_brush_size(+1)
        assert new == 13
        assert int(ws._state.brush.size) == 13   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_step_brush_size_decrement(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_brush(size=12)   # noqa: SLF001
        new = ws.step_brush_size(-1)
        assert new == 11
        assert int(ws._state.brush.size) == 11   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_step_brush_size_clamps_to_minimum(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_brush(size=2)   # noqa: SLF001
        ws.step_brush_size(-50)
        assert int(ws._state.brush.size) == ws.BRUSH_SIZE_MIN   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_step_brush_size_clamps_to_maximum(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_brush(size=480)   # noqa: SLF001
        ws.step_brush_size(+999)
        assert int(ws._state.brush.size) == ws.BRUSH_SIZE_MAX   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_step_brush_size_at_max_is_idempotent(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_brush(size=ws.BRUSH_SIZE_MAX)   # noqa: SLF001
        new = ws.step_brush_size(+1)
        # No further increase past the cap, helper returns the cap.
        assert new == ws.BRUSH_SIZE_MAX
    finally:
        ws.deleteLater()


def test_step_brush_size_returns_zero_when_state_missing(qapp):
    """The helper must degrade gracefully if ``_state`` was never built —
    a no-state shortcut press shouldn't crash the app."""
    ws = PaintWorkspace()
    try:
        ws._state = None    # noqa: SLF001
        assert ws.step_brush_size(+1) == 0
    finally:
        ws.deleteLater()
