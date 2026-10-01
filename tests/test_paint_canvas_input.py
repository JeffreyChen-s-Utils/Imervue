"""Tests for the paint canvas's pointer input: pen pressure and mouse pressure.

The mixin methods run on small stand-ins (no PaintCanvas, which is a
QOpenGLWidget), so this file runs on headless CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.paint.canvas_input import PaintCanvasInputMixin
from Imervue.paint.pressure_curve import HARD_FLOOR, PressureCurve


@pytest.mark.parametrize(("state", "raw", "expected"), [
    (None, 0.3, 0.3),
    (SimpleNamespace(pressure_curve=PressureCurve()), 0.3, 0.3),
    (SimpleNamespace(pressure_curve=HARD_FLOOR), 0.0, 0.4),
    (SimpleNamespace(pressure_curve=HARD_FLOOR), 0.1, 0.45),
    (SimpleNamespace(pressure_curve=HARD_FLOOR), 1.0, 1.0),
])
def test_pen_pressure_follows_the_curve(state, raw, expected):
    """Settings > Pressure Curve stored a curve that no stroke ever used."""
    host = SimpleNamespace(_tool_state_for_hud=state)
    assert PaintCanvasInputMixin._pen_pressure(host, raw) == pytest.approx(expected)  # noqa: SLF001


def test_a_mouse_stroke_is_drawn_at_full_pressure():
    """The pen's last pressure (0 when lifted) used to thin every later mouse stroke."""
    sent = []
    host = SimpleNamespace(
        _last_pressure=0.0,
        _dispatch_pointer=lambda phase, x, y, **kw: sent.append((phase, x, y, kw["pressure"])),
    )
    event = SimpleNamespace(
        position=lambda: SimpleNamespace(x=lambda: 4.0, y=lambda: 5.0),
        button=lambda: SimpleNamespace(value=1),
        modifiers=lambda: SimpleNamespace(value=0),
    )
    PaintCanvasInputMixin._dispatch(host, "press", event)  # noqa: SLF001
    assert sent == [("press", 4.0, 5.0, 1.0)]
