"""Brush stroke input stabiliser.

A jittery hand or a low-resolution mouse produces noisy pointer
events. The stabiliser runs each event through an exponential moving
average so the brush follows a smoothed cursor rather than the raw
input. MediBang exposes this as the "stabiliser" slider; we mirror
it as a per-brush setting in :class:`Imervue.paint.tool_state.BrushSettings`.

Strength 0 means no smoothing (alpha=1, output equals input). Strength
1 effectively freezes the brush; we cap the practical maximum at 0.95
so the cursor still keeps up. End-of-stroke calls :meth:`flush` so the
brush walks from its smoothed position to the actual release point
instead of stranding the line short.
"""
from __future__ import annotations

import math

STRENGTH_MIN = 0.0
STRENGTH_MAX = 1.0
_PRACTICAL_MAX = 0.95
_FLUSH_STEPS = 24            # Max EMA steps emitted by flush()
_FLUSH_TOLERANCE = 0.5       # px — flush stops once the lag drops below this


class StrokeStabilizer:
    """Stateful EMA filter for one brush stroke."""

    def __init__(self, strength: float = 0.0):
        s = max(STRENGTH_MIN, min(_PRACTICAL_MAX, float(strength)))
        # alpha is the per-step blend factor toward the input. strength=0
        # gives alpha=1 (no smoothing); strength=0.95 gives alpha=0.05.
        self._alpha = 1.0 - s
        self._x: float | None = None
        self._y: float | None = None

    @property
    def alpha(self) -> float:
        return self._alpha

    def begin(self, x: float, y: float) -> tuple[float, float]:
        """Reset the filter to ``(x, y)`` and return that pair unchanged."""
        self._x = float(x)
        self._y = float(y)
        return (self._x, self._y)

    def step(self, x: float, y: float) -> tuple[float, float]:
        """Feed one point and return the smoothed position."""
        if self._x is None or self._y is None:
            return self.begin(x, y)
        self._x += (float(x) - self._x) * self._alpha
        self._y += (float(y) - self._y) * self._alpha
        return (self._x, self._y)

    def flush(self, x: float, y: float) -> list[tuple[float, float]]:
        """Drain residual lag toward ``(x, y)``.

        Returns a list of intermediate points the dispatcher should
        stamp before ending the stroke. With strength 0 the list has
        one element (``(x, y)`` exactly); with strength near 1 it can
        return up to ``_FLUSH_STEPS`` points walking toward the target.
        """
        if self._x is None or self._y is None:
            self.begin(x, y)
            return [(self._x, self._y)]   # type: ignore[arg-type]
        if self._alpha >= 1.0:
            self._x = float(x)
            self._y = float(y)
            return [(self._x, self._y)]
        out: list[tuple[float, float]] = []
        for _ in range(_FLUSH_STEPS):
            self._x += (float(x) - self._x) * self._alpha
            self._y += (float(y) - self._y) * self._alpha
            out.append((self._x, self._y))
            if (math.fabs(self._x - x) < _FLUSH_TOLERANCE
                    and math.fabs(self._y - y) < _FLUSH_TOLERANCE):
                break
        # Always finish exactly on the cursor so the visible stroke
        # ends where the user released the button.
        if out and (out[-1][0] != x or out[-1][1] != y):
            self._x = float(x)
            self._y = float(y)
            out.append((self._x, self._y))
        return out
