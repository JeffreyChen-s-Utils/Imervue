"""Fixed-step physics clock, output changes and visibility lifecycle."""
from __future__ import annotations

from Imervue.puppet.canvas_rig import refresh_rig

import time
from Imervue.puppet.physics import PhysicsEngine
from Imervue.puppet.canvas_rig import expression_values

_PHYSICS_INTERVAL_MS = 16
_PHYSICS_STEP = 1 / 60
_PHYSICS_MAX_DT = 0.05
_PHYSICS_REDRAW_THRESHOLD = 1e-4

def _outputs_close(new: dict[str, float], old: dict[str, float]) -> bool:
    """Whether two physics output maps differ by less than the redraw threshold."""
    return new.keys() == old.keys() and all(
        abs(value - old[key]) < _PHYSICS_REDRAW_THRESHOLD for key, value in new.items())


class PuppetCanvasPhysicsMixin:
    """Fixed-step physics clock, output changes and visibility lifecycle."""

    def step_physics(self, dt: float, steps: int = 1) -> None:
        """Advance the physics chains ``steps`` times by ``dt`` seconds and
        re-fold their outputs into the deformed-vertex cache once.

        The canvas's own physics clock calls this (see
        :meth:`_sync_physics_timer`). Outputs that moved less than the
        redraw threshold leave the vertices and the frame alone.
        """
        if self._document is None or steps < 1:
            return
        active_values = expression_values(self)
        for _step in range(steps):
            outputs = self._physics.step(dt, active_values)
        if _outputs_close(outputs, self._physics_outputs):
            return
        self._physics_outputs = outputs
        refresh_rig(self)

    def reset_physics(self) -> None:
        """Snap every physics chain back to rest and drop its outputs."""
        self._physics.reset()
        self._physics_outputs = {}
        refresh_rig(self)

    def _sync_physics_timer(self) -> None:
        """Run the physics clock only while a shown rig has physics chains."""
        wanted = bool(self._physics.chain_ids()) and self.isVisible()
        if wanted == self._physics_timer.isActive():
            return
        if wanted:
            self._physics_clock = None
            self._physics_lag = 0.0
            self._physics_timer.start()
        else:
            self._physics_timer.stop()

    def _on_physics_tick(self) -> None:
        """Step the chains in fixed steps for the real time since the last tick."""
        now = time.monotonic()
        last, self._physics_clock = self._physics_clock, now
        if last is None:
            return
        self._physics_lag += min(now - last, _PHYSICS_MAX_DT)
        steps = int(self._physics_lag // _PHYSICS_STEP)
        if steps:
            self._physics_lag = max(0.0, self._physics_lag - steps * _PHYSICS_STEP)
            self.step_physics(_PHYSICS_STEP, steps)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._sync_physics_timer()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().hideEvent(event)
        self._sync_physics_timer()

    def physics(self) -> PhysicsEngine:
        return self._physics
