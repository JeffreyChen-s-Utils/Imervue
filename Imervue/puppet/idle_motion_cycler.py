"""Idle motion cycler — Cubism ``CubismMotionManager``-style.

The existing :class:`IdleDriver` handles *parameter-level* idle motion
(continuous breath + drift on ``ParamBreath`` / head / body angles).
This module covers the *motion-level* idle: when the rig is otherwise
sitting still, periodically pick a random :class:`Motion` whose
:attr:`Motion.group` matches ``Idle`` (or any configurable group) and
play it through the bound :class:`MotionPlayer`. The player's own
fade-in / fade-out smooths the cross-over between picks.

Yields gracefully:

* When a HitArea or the user manually plays a non-Idle motion, the
  cycler stays out of the way — its watchdog only fires when the
  active motion belongs to the configured idle group (or the player
  is idle).
* When the document carries no Idle motions, the cycler is a no-op
  rather than an error — rigs without authored idles still work.
"""
from __future__ import annotations

import logging
import secrets
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.document import Motion

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.motion_player import MotionPlayer

logger = logging.getLogger("Imervue.plugin.puppet.idle_motion_cycler")

DEFAULT_CYCLE_DURATION_S: float = 8.0
"""Seconds between picks. Tunable per-instance via
:meth:`IdleMotionCycler.set_cycle_duration` — 8s is long enough that
short idle motions fully play through their fade-in / fade-out and
short enough that the rig never feels frozen."""

_TICK_HZ: int = 2
"""Watchdog tick rate. Higher rates burn cycles for no visible win;
lower rates make the cycler feel sluggish to enable / disable."""


class IdleMotionCycler(QObject):
    """Periodically pick a random idle-group motion and play it."""

    state_changed = Signal()

    def __init__(
        self,
        player: MotionPlayer,
        canvas: PuppetCanvas,
        parent=None,
        *,
        group: str = "Idle",
    ):
        super().__init__(parent)
        self._player = player
        self._canvas = canvas
        self._group = group
        self._enabled = False
        self._cycle_duration_s = DEFAULT_CYCLE_DURATION_S
        self._last_pick_t: float = 0.0
        self._last_motion_name: str | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _TICK_HZ))
        self._timer.timeout.connect(self._on_tick)

    # ---- public ----------------------------------------------------

    def is_enabled(self) -> bool:
        return self._enabled

    def group(self) -> str:
        return self._group

    def cycle_duration(self) -> float:
        return self._cycle_duration_s

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self._enabled:
            return
        self._enabled = bool(enabled)
        if enabled:
            # Pick something immediately on enable so the user sees
            # the cycler work without waiting for the first interval.
            self._last_pick_t = 0.0
            self._timer.start()
        else:
            self._timer.stop()
        self.state_changed.emit()

    def set_group(self, group: str) -> None:
        self._group = str(group)

    def set_cycle_duration(self, seconds: float) -> None:
        self._cycle_duration_s = max(0.5, float(seconds))

    def shutdown(self) -> None:
        self._timer.stop()

    def pick_next(self) -> Motion | None:
        """Manual one-shot pick — used by tests and by the workspace
        when a user clicks "next idle". Returns the motion that was
        bound, or ``None`` when no idle motion is available."""
        return self._pick_next()

    # ---- watchdog --------------------------------------------------

    def _on_tick(self) -> None:
        if not self._enabled or self._canvas.document() is None:
            return
        if self._should_yield():
            # Reset our clock while we wait — once the user/HitArea
            # motion finishes, the cycler resumes from a fresh start.
            self._last_pick_t = time.monotonic()
            return
        elapsed = time.monotonic() - self._last_pick_t
        if elapsed < self._cycle_duration_s and self._player.motion() is not None:
            return
        self._pick_next()

    def _should_yield(self) -> bool:
        """Return ``True`` when the player is currently driving a
        motion that doesn't belong to our idle group — i.e. someone
        else is in control and we shouldn't interrupt."""
        motion = self._player.motion()
        if motion is None:
            return False
        if not self._player.is_playing() and not self._player.is_fading_out():
            return False
        return motion.group != self._group

    def _pick_next(self) -> Motion | None:
        document = self._canvas.document()
        if document is None:
            return None
        candidates = [m for m in document.motions if m.group == self._group]
        if not candidates:
            return None
        # Avoid back-to-back replay when alternatives exist — keeps
        # the loop feeling varied even with two or three Idle motions.
        if len(candidates) > 1 and self._last_motion_name is not None:
            filtered = [m for m in candidates if m.name != self._last_motion_name]
            if filtered:
                candidates = filtered
        picked = (
            candidates[0]
            if len(candidates) == 1
            else secrets.choice(candidates)
        )
        self._player.set_motion(picked)
        self._player.play()
        self._last_pick_t = time.monotonic()
        self._last_motion_name = picked.name
        logger.debug("idle cycler picked %s", picked.name)
        return picked
