"""Geometry for the ▶ play badge drawn over video thumbnails.

Pure float math so badge placement can be unit-tested without a GL context.
The actual drawing lives in :mod:`tile_grid_renderer`, whose GL path the
headless CI cannot exercise.
"""
from __future__ import annotations

from dataclasses import dataclass

# Badge disc sizing, relative to the shorter tile side, then clamped.
_BADGE_RADIUS_FRACTION = 0.16
_BADGE_RADIUS_MIN = 9.0
_BADGE_RADIUS_MAX = 30.0

# Play-triangle proportions, relative to the badge radius.
_TRI_HALF_HEIGHT = 0.52   # half the flat back edge
_TRI_BACK = 0.40          # centre → flat back edge
_TRI_TIP = 0.62           # centre → pointing tip
_TRI_NUDGE = 0.08         # shift right so the triangle reads optically centred

_Point = tuple[float, float]


@dataclass(frozen=True)
class VideoBadge:
    """Resolved screen geometry for one play badge."""

    cx: float
    cy: float
    radius: float
    triangle: tuple[_Point, _Point, _Point]


def video_badge_radius(width: float, height: float) -> float:
    """Badge disc radius for a tile of the given size, clamped to sane bounds."""
    shorter = min(abs(width), abs(height))
    return max(
        _BADGE_RADIUS_MIN,
        min(_BADGE_RADIUS_MAX, shorter * _BADGE_RADIUS_FRACTION),
    )


def video_badge_geometry(x0: float, y0: float, x1: float, y1: float) -> VideoBadge:
    """Centre disc + right-pointing play triangle for a tile rectangle.

    The triangle is nudged slightly right so its visual mass sits centred,
    and every vertex stays inside the disc radius.
    """
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    radius = video_badge_radius(x1 - x0, y1 - y0)
    nudge = radius * _TRI_NUDGE
    tip: _Point = (cx + radius * _TRI_TIP + nudge, cy)
    top: _Point = (cx - radius * _TRI_BACK + nudge, cy - radius * _TRI_HALF_HEIGHT)
    bottom: _Point = (cx - radius * _TRI_BACK + nudge, cy + radius * _TRI_HALF_HEIGHT)
    return VideoBadge(cx, cy, radius, (tip, top, bottom))
