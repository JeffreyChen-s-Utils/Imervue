"""Idle motion driver — passive parameter motion when nothing else is
pumping values into the canvas.

A Live2D-feel rig is *never* perfectly still: even between motions the
chest rises with breath and the head drifts a few degrees. This module
ships the math (so it's pure-Python testable) plus a Qt QObject wrapper
that runs a QTimer and pushes per-tick values into the bound canvas.

The pure helpers — :func:`breath_curve_value`, :func:`idle_drift_value` —
have no Qt / no global state and take time as input, so callers can
deterministically sample at any ``t`` for tests or off-line rendering.

The :class:`IdleDriver` Qt wrapper toggles on/off and only pushes into
parameters the document actually has; missing standard ids are skipped
silently so an exotic rig that omits e.g. ``ParamBreath`` still works
fine.
"""
from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Y,
    PARAM_ANGLE_Z,
    PARAM_BODY_ANGLE_X,
    PARAM_BODY_ANGLE_Z,
    PARAM_BREATH,
)

if TYPE_CHECKING:
    from puppet.canvas import PuppetCanvas

# Public so tests and tuning UIs can reference the values.
BREATH_PERIOD_S: float = 3.5
"""Chest rise + fall cycle. ~17 breaths / minute — close to a resting
adult's rate."""

DRIFT_PERIODS: dict[str, float] = {
    PARAM_ANGLE_X: 9.7,
    PARAM_ANGLE_Y: 12.3,
    PARAM_ANGLE_Z: 17.1,
    PARAM_BODY_ANGLE_X: 14.5,
    PARAM_BODY_ANGLE_Z: 21.7,
}
"""Per-parameter sine periods (s). Intentionally irrational ratios so
the parameters don't lock into a visible pattern."""

DRIFT_AMPLITUDE: float = 0.08
"""Peak drift amplitude as a fraction of each param's ``[-1, 1]``
range. ``0.08`` reads as "alive but not animated" in tests with the
default rig."""

_IDLE_TICK_HZ: int = 30


def breath_curve_value(elapsed_sec: float, *, period: float = BREATH_PERIOD_S) -> float:
    """Return the breath parameter value at ``elapsed_sec`` — a smooth
    half-cosine that maps to ``[0, 1]`` with ``0`` at the start of the
    cycle (full exhale) and ``1`` at the midpoint (full inhale).

    Resilient to non-positive ``period`` (returns the neutral midpoint
    so a misconfigured rig doesn't push NaNs into the parameter dict).
    """
    if period <= 0.0:
        return 0.5
    phase = (float(elapsed_sec) % period) / period
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)


def idle_drift_value(
    elapsed_sec: float,
    *,
    period: float,
    amplitude: float = DRIFT_AMPLITUDE,
    phase_offset: float = 0.0,
) -> float:
    """Return a smooth sine drift in ``[-amplitude, amplitude]`` at
    ``elapsed_sec``. ``phase_offset`` lets the caller decorrelate
    multiple drivers that share a period."""
    if period <= 0.0:
        return 0.0
    omega = 2.0 * math.pi / period
    return float(amplitude) * math.sin(omega * float(elapsed_sec) + float(phase_offset))


def idle_parameter_values(elapsed_sec: float) -> dict[str, float]:
    """Compose all idle parameter values at ``elapsed_sec`` into a
    ``{param_id: value}`` map. Pure helper — Qt callers just push the
    map into the canvas; tests inspect it directly."""
    out: dict[str, float] = {PARAM_BREATH: breath_curve_value(elapsed_sec)}
    for i, (param_id, period) in enumerate(DRIFT_PERIODS.items()):
        out[param_id] = idle_drift_value(
            elapsed_sec, period=period, phase_offset=i * math.pi / 3.0,
        )
    return out


class IdleDriver(QObject):
    """QObject that pumps idle parameter values into a canvas while
    enabled. The workspace toggles this on/off from a toolbar action."""

    state_changed = Signal()

    def __init__(self, canvas: PuppetCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._enabled = False
        self._anchor: float = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _IDLE_TICK_HZ))
        self._timer.timeout.connect(self._on_tick)

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self._enabled:
            return
        self._enabled = bool(enabled)
        if enabled:
            self._anchor = time.monotonic()
            self._timer.start()
        else:
            self._timer.stop()
        self.state_changed.emit()

    def shutdown(self) -> None:
        self._timer.stop()

    def _on_tick(self) -> None:
        if not self._enabled or self._canvas.document() is None:
            return
        elapsed = time.monotonic() - self._anchor
        values = idle_parameter_values(elapsed)
        canvas_values = self._canvas.parameter_values()
        for param_id, value in values.items():
            if param_id in canvas_values:
                self._canvas.set_parameter_value(param_id, value)
