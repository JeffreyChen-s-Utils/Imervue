"""Wall-level "loading" state and spinner geometry for the tile grid.

Opening a folder empties the wall immediately (``load_tile_grid_async([])``)
and only refills it when the first scan batch lands, so a slow drive, a network
share, or a very large folder leaves the canvas blank with no feedback at all.
:func:`should_show_wall_loading` decides when that blank phase deserves a
centred spinner; :func:`spinner_dots` supplies the same rotating-dot geometry
the per-tile placeholders use, so both animations stay visually identical.

Pure math — no Qt, no GL — so the policy and the geometry are unit-testable.
"""

from __future__ import annotations

import math

# Four dots on an orbit, the densest ring that still reads as "rotating" at the
# 80 ms placeholder tick without looking like a solid circle.
SPINNER_DOT_COUNT = 4
# Orbit radius / dot radius as multiples of the caller's nominal radius.
_ORBIT_RATIO = 1.6
_DOT_RATIO = 1 / 3
# Trailing dots fade out so the ring reads as spinning in one direction.
_ALPHA_MIN = 80
_ALPHA_MAX = 200

# Centred wall spinner: a fraction of the shorter canvas edge, clamped so it
# stays visible on a narrow dock and doesn't dominate a maximised window.
_WALL_RADIUS_RATIO = 0.05
_WALL_RADIUS_MIN = 14.0
_WALL_RADIUS_MAX = 34.0

# One full revolution per second.
_SPIN_PERIOD_S = 1.0


def should_show_wall_loading(tile_grid_mode: bool, image_count: int,
                             scan_active: bool) -> bool:
    """Whether the tile wall should show its centred "loading" spinner.

    Only during the genuinely blank phase: the wall is on screen, a folder scan
    is still running, and no image has arrived yet. Once the first batch lands
    every slot draws its own placeholder spinner, so a second wall-level one
    would just be noise — and an idle wall with no images is an empty folder,
    not a slow one.
    """
    return bool(tile_grid_mode) and bool(scan_active) and int(image_count) <= 0


def spinner_phase(now: float, period_s: float = _SPIN_PERIOD_S) -> float:
    """Rotation angle (radians) of the spinner at monotonic time *now*.

    Wraps every *period_s* seconds so the angle stays small regardless of how
    long the process has been running. A non-positive period would divide by
    zero, so it falls back to the default.
    """
    period = period_s if period_s > 0 else _SPIN_PERIOD_S
    return (now % period) / period * 2 * math.pi


def spinner_dots(center_x: float, center_y: float, radius: float, phase: float,
                 count: int = SPINNER_DOT_COUNT
                 ) -> list[tuple[float, float, float, int]]:
    """Return ``(x, y, dot_radius, alpha)`` for each dot of the spinner ring.

    *radius* is the nominal size; dots orbit at ``radius * 1.6`` and are drawn
    at ``radius / 3``. Alpha ramps from :data:`_ALPHA_MIN` on the leading dot to
    :data:`_ALPHA_MAX` on the trailing one. A *count* below 1 yields no dots.
    """
    if count < 1:
        return []
    orbit = radius * _ORBIT_RATIO
    dot_radius = radius * _DOT_RATIO
    step = 2 * math.pi / count
    dots = []
    for i in range(count):
        angle = phase + i * step
        # A lone dot has no trail to fade against, so it takes the full alpha
        # rather than the leading dot's faint end of the ramp.
        ratio = i / (count - 1) if count > 1 else 1.0
        alpha = _ALPHA_MIN + int((_ALPHA_MAX - _ALPHA_MIN) * ratio)
        dots.append((
            center_x + orbit * math.cos(angle),
            center_y + orbit * math.sin(angle),
            dot_radius,
            alpha,
        ))
    return dots


def wall_spinner_geometry(width: int, height: int) -> tuple[float, float, float]:
    """Return ``(center_x, center_y, radius)`` for the centred wall spinner.

    The radius is clamped to a sane band so the spinner never disappears on a
    tiny canvas nor swells to fill a large one.
    """
    scale = min(max(0, int(width)), max(0, int(height))) * _WALL_RADIUS_RATIO
    radius = min(max(scale, _WALL_RADIUS_MIN), _WALL_RADIUS_MAX)
    return width / 2, height / 2, radius
