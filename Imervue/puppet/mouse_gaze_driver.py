"""Mouse-gaze driver — pet head + eyes follow the cursor.

A natural way to make a desktop pet feel "aware" without rigging a
webcam: track the cursor's screen position relative to the pet's
on-screen center, and drive the four standard look-at parameters
(:data:`PARAM_ANGLE_X`, :data:`PARAM_ANGLE_Y`, :data:`PARAM_EYE_BALL_X`,
:data:`PARAM_EYE_BALL_Y`) toward it. The eye-ball saturates before the
head — same heuristic Live2D's stock samples use, so the eyes lead
and the neck follows.

The pure helpers (:func:`gaze_target_values`, :func:`smoothed_value`)
have no Qt dependency and take time / position as input, so tests
sample them deterministically. The :class:`MouseGazeDriver` Qt wrapper
polls the cursor at a fixed rate, smooths the result with exponential
decay, and pushes the survivors into the canvas; missing standard
params are skipped silently so an exotic rig that omits e.g.
``ParamEyeBallY`` still works.
"""
from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QCursor

from Imervue.puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Y,
    PARAM_EYE_BALL_X,
    PARAM_EYE_BALL_Y,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.puppet.mouse_gaze_driver")

DEFAULT_HEAD_TRACK_RADIUS_PX: float = 600.0
"""Cursor distance from pet center (px) at which head params saturate
at ``±1``. Wider radius = pet looks calmer; narrower = more reactive."""

DEFAULT_EYE_TRACK_RADIUS_PX: float = 250.0
"""Eye-ball saturation distance. Smaller than the head radius so the
eyes lead the head — a classic Live2D detail."""

DEFAULT_SMOOTHING_S: float = 0.18
"""Exponential-decay time constant. ~180 ms feels natural: the head
doesn't lag enough to look broken, but never jitters either."""

_TICK_HZ: int = 30


def _clamp_unit(value: float) -> float:
    """Clamp ``value`` to ``[-1, 1]``. Kept private because every
    parameter in this module shares the same range — exposing a
    configurable clamp would just invite callers to misuse it."""
    if value < -1.0:
        return -1.0
    if value > 1.0:
        return 1.0
    return float(value)


def gaze_target_values(
    cursor_offset_px: tuple[float, float],
    *,
    head_radius_px: float = DEFAULT_HEAD_TRACK_RADIUS_PX,
    eye_radius_px: float = DEFAULT_EYE_TRACK_RADIUS_PX,
) -> dict[str, float]:
    """Map cursor offset ``(dx, dy)`` from the pet center (screen
    pixels, Y-down) to the four look-at parameters.

    Y is flipped: cursor-above-pet → positive ``ParamAngleY`` /
    ``ParamEyeBallY`` (Cubism convention is +Y is up). Each axis
    clamps to ``[-1, 1]`` after scaling.

    Robust to ``radius_px <= 0`` (returns neutral zeros) so a
    misconfigured caller never pushes NaNs into the rig.
    """
    dx, dy = float(cursor_offset_px[0]), float(cursor_offset_px[1])
    head_x = _clamp_unit(dx / head_radius_px) if head_radius_px > 0 else 0.0
    head_y = _clamp_unit(-dy / head_radius_px) if head_radius_px > 0 else 0.0
    eye_x = _clamp_unit(dx / eye_radius_px) if eye_radius_px > 0 else 0.0
    eye_y = _clamp_unit(-dy / eye_radius_px) if eye_radius_px > 0 else 0.0
    return {
        PARAM_ANGLE_X: head_x,
        PARAM_ANGLE_Y: head_y,
        PARAM_EYE_BALL_X: eye_x,
        PARAM_EYE_BALL_Y: eye_y,
    }


def smoothed_value(
    current: float, target: float, *, dt_s: float, tau_s: float,
) -> float:
    """Move ``current`` toward ``target`` with exponential decay.

    ``alpha = 1 - exp(-dt/tau)`` — frame-rate-independent, so the
    perceived response time stays constant whether the driver runs
    at 30 Hz or 60 Hz.

    Special cases (snap to target):
    * ``tau_s <= 0`` — caller opted out of smoothing.
    * ``dt_s <= 0`` — first tick or clock skew; we just adopt the
      target rather than freezing on stale state.
    """
    if tau_s <= 0.0 or dt_s <= 0.0:
        return float(target)
    alpha = 1.0 - math.exp(-float(dt_s) / float(tau_s))
    return float(current) + (float(target) - float(current)) * alpha


class MouseGazeDriver(QObject):
    """Polls the cursor and drives look-at parameters on a canvas.

    Constructed once, toggled on / off with :meth:`set_enabled`. The
    bound ``widget`` is whatever owns the pet's on-screen rectangle
    — usually the :class:`PetWindow` itself; the driver reads its
    ``frameGeometry`` to know where "center" is.
    """

    state_changed = Signal()

    def __init__(
        self,
        canvas: PuppetCanvas,
        widget: QWidget,
        parent=None,
    ):
        super().__init__(parent)
        self._canvas = canvas
        self._widget = widget
        self._enabled = False
        self._head_radius_px = DEFAULT_HEAD_TRACK_RADIUS_PX
        self._eye_radius_px = DEFAULT_EYE_TRACK_RADIUS_PX
        self._tau_s = DEFAULT_SMOOTHING_S
        self._last_tick: float = 0.0
        self._smoothed: dict[str, float] = {
            PARAM_ANGLE_X: 0.0,
            PARAM_ANGLE_Y: 0.0,
            PARAM_EYE_BALL_X: 0.0,
            PARAM_EYE_BALL_Y: 0.0,
        }
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _TICK_HZ))
        self._timer.timeout.connect(self._on_tick)

    # ---- public ----------------------------------------------------

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self._enabled:
            return
        self._enabled = bool(enabled)
        if enabled:
            self._last_tick = time.monotonic()
            self._timer.start()
        else:
            self._timer.stop()
        self.state_changed.emit()

    def set_smoothing(self, tau_s: float) -> None:
        self._tau_s = max(0.0, float(tau_s))

    def smoothing(self) -> float:
        return self._tau_s

    def set_head_radius(self, radius_px: float) -> None:
        self._head_radius_px = max(1.0, float(radius_px))

    def head_radius(self) -> float:
        return self._head_radius_px

    def set_eye_radius(self, radius_px: float) -> None:
        self._eye_radius_px = max(1.0, float(radius_px))

    def eye_radius(self) -> float:
        return self._eye_radius_px

    def shutdown(self) -> None:
        self._timer.stop()

    def smoothed_values(self) -> dict[str, float]:
        """Test hook — current smoothed state without forcing a tick."""
        return dict(self._smoothed)

    def tick_once(self) -> None:
        """Test / debug hook — run a single tick without waiting for
        the QTimer. Useful in headless tests where the event loop
        isn't spinning."""
        self._on_tick()

    # ---- internal --------------------------------------------------

    def _cursor_offset_px(self) -> tuple[float, float]:
        """Return ``(dx, dy)`` from the widget's on-screen center to
        the current cursor in *global* pixels (the cursor usually
        lives outside the pet's rectangle). Returns ``(0, 0)`` when
        the widget has no valid geometry yet, so the driver doesn't
        push junk during the brief construction window before show."""
        widget = self._widget
        if widget is None or not widget.isVisible():
            return (0.0, 0.0)
        frame = widget.frameGeometry()
        if frame.width() <= 0 or frame.height() <= 0:
            return (0.0, 0.0)
        cx = frame.x() + frame.width() / 2.0
        cy = frame.y() + frame.height() / 2.0
        cursor = QCursor.pos()
        return (float(cursor.x() - cx), float(cursor.y() - cy))

    def _on_tick(self) -> None:
        if not self._enabled or self._canvas.document() is None:
            return
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        target = gaze_target_values(
            self._cursor_offset_px(),
            head_radius_px=self._head_radius_px,
            eye_radius_px=self._eye_radius_px,
        )
        canvas_values = self._canvas.parameter_values()
        batch: dict[str, float] = {}
        for pid, target_v in target.items():
            cur = self._smoothed.get(pid, 0.0)
            new = smoothed_value(cur, target_v, dt_s=dt, tau_s=self._tau_s)
            self._smoothed[pid] = new
            if pid in canvas_values:
                batch[pid] = new
        if batch:
            self._canvas.set_parameter_values(batch)
