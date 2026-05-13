"""Pure-numpy symmetry helper for the brush tool.

The Paint workspace mirrors live brush strokes across one or more
axes — raster paint apps exposes this as the symmetry tool. Each mirror mode
maps a single pointer position to a list of points that the brush
dispatcher then stamps in lock-step.

* ``off`` — no mirror; just the source point.
* ``horizontal`` — flip across the vertical axis through the origin
  (left↔right).
* ``vertical`` — flip across the horizontal axis through the origin
  (top↔bottom).
* ``both`` — both flips (4 strokes total: source + 3 mirrors).
* ``radial_4`` — rotate around the origin by 90° / 180° / 270°.
* ``radial_8`` — rotate by 45° steps (8 strokes total).

Pure numpy / math; no Qt — testable without a display server. The
origin defaults to the canvas centre but the workspace can override
it for off-centre symmetry.
"""
from __future__ import annotations

import math

SYMMETRY_MODES = (
    "off",
    "horizontal",
    "vertical",
    "both",
    "radial_4",
    "radial_8",
)
DEFAULT_SYMMETRY_MODE = "off"


def mirror_points(
    point: tuple[float, float],
    mode: str,
    origin: tuple[float, float],
) -> list[tuple[float, float]]:
    """Return the source point + every mirror produced by ``mode``.

    The source point is always first in the returned list; mirrors
    follow in a stable order so consecutive calls with the same input
    produce identical brush-stroke groupings.
    """
    if mode not in SYMMETRY_MODES:
        raise ValueError(
            f"unknown symmetry mode {mode!r}; expected one of {SYMMETRY_MODES}",
        )
    x, y = float(point[0]), float(point[1])
    ox, oy = float(origin[0]), float(origin[1])
    if mode == "off":
        return [(x, y)]
    if mode == "horizontal":
        return [(x, y), (2.0 * ox - x, y)]
    if mode == "vertical":
        return [(x, y), (x, 2.0 * oy - y)]
    if mode == "both":
        return [
            (x, y),
            (2.0 * ox - x, y),
            (x, 2.0 * oy - y),
            (2.0 * ox - x, 2.0 * oy - y),
        ]
    if mode == "radial_4":
        return _rotate_around(x, y, ox, oy, [0, 90, 180, 270])
    return _rotate_around(x, y, ox, oy, [0, 45, 90, 135, 180, 225, 270, 315])


def _rotate_around(
    x: float, y: float, ox: float, oy: float, angles_deg: list[int],
) -> list[tuple[float, float]]:
    """Rotate ``(x, y)`` around ``(ox, oy)`` by each angle in degrees."""
    out: list[tuple[float, float]] = []
    rel_x = x - ox
    rel_y = y - oy
    for angle in angles_deg:
        radians = math.radians(angle)
        cos_a = math.cos(radians)
        sin_a = math.sin(radians)
        rx = rel_x * cos_a - rel_y * sin_a
        ry = rel_x * sin_a + rel_y * cos_a
        out.append((rx + ox, ry + oy))
    return out
