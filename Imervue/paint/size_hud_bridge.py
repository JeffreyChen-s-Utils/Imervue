"""Wire bracket-key shortcuts to brush-size changes + HUD bumps.

Pure-logic bridge so the wiring (KeyEvent → state.set_brush → HUD
state.bump) can be tested without a Qt key-event loop.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from Imervue.paint.tool_state import BRUSH_SIZE_MAX, BRUSH_SIZE_MIN

if TYPE_CHECKING:
    from Imervue.paint.size_hud import SizeHudState
    from Imervue.paint.tool_state import ToolState

# Bracket key bumps the brush size by a percentage of the current
# value so each press feels proportional — pressing ``[`` on a 4 px
# brush moves to 3 px, on a 200 px brush moves to 170 px.
DEFAULT_BUMP_FRACTION = 0.15
MIN_BUMP_PIXELS = 1


def adjust_brush_size(
    state: ToolState,
    *,
    larger: bool,
    fraction: float = DEFAULT_BUMP_FRACTION,
) -> int:
    """Return the new brush size after a single bracket-key bump.

    ``larger=True`` corresponds to the ``]`` key; ``False`` to ``[``.
    The result is also written back into the state via
    :meth:`ToolState.set_brush` so the caller can read it from there.
    Clamped into ``[BRUSH_SIZE_MIN, BRUSH_SIZE_MAX]`` so a long key
    repeat at the limits doesn't drift past the documented range.
    """
    if not 0.0 < float(fraction) <= 1.0:
        raise ValueError(
            f"fraction must be in (0, 1], got {fraction!r}",
        )
    current = int(state.brush.size)
    bump = max(MIN_BUMP_PIXELS, int(round(current * float(fraction))))
    target = current + bump if larger else current - bump
    target = max(BRUSH_SIZE_MIN, min(BRUSH_SIZE_MAX, target))
    state.set_brush(size=int(target))
    return int(target)


def trigger_size_hud(
    state: ToolState,
    hud: SizeHudState,
    *,
    now: float | None = None,
) -> None:
    """Bump the size HUD with the brush's current size.

    Decoupled from :func:`adjust_brush_size` so a UI that shows the
    HUD when the user changes the size via a slider (not just the
    bracket keys) can call this in isolation.
    """
    timestamp = float(now) if now is not None else time.monotonic()
    hud.bump(size=int(state.brush.size), now=timestamp)
