"""Polyline offset — the parallel curve of a path (stroke-to-outline).

The geometry building block GIMP/Krita vector layers use to turn a centre-line
stroke into a fixed-width outline: shift every segment along its normal by a
fixed distance and join the shifted segments. Interior corners use a miter join,
falling back to a bevel (two points) once the miter would shoot out past
``miter_limit`` times the offset — the same rule SVG ``stroke-linejoin`` follows.

Pure-math, Qt-free, ``(x, y)`` float tuples in and out. A positive *distance*
offsets to the left of travel; a negative one to the right.
"""
from __future__ import annotations

import math

Point = tuple[float, float]

_MIN_POINTS = 2
_DEGENERATE = 1e-9


def offset_polyline(
    points: list[Point], distance: float, miter_limit: float = 4.0,
) -> list[Point]:
    """Return the polyline parallel to *points* at *distance*.

    Consecutive duplicate points are collapsed first. Interior vertices get a
    miter join, or a two-point bevel when the miter length exceeds
    *miter_limit* × ``abs(distance)``. Raises ``ValueError`` for fewer than two
    distinct points.
    """
    pts = _dedupe(points)
    if len(pts) < _MIN_POINTS:
        raise ValueError("offset_polyline needs at least two distinct points")
    normals = [_left_normal(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    result: list[Point] = [_shift(pts[0], normals[0], distance)]
    for i in range(1, len(pts) - 1):
        result.extend(_join(pts[i], normals[i - 1], normals[i], distance, miter_limit))
    result.append(_shift(pts[-1], normals[-1], distance))
    return result


def _join(
    vertex: Point, n_prev: Point, n_next: Point, distance: float, miter_limit: float,
) -> list[Point]:
    """Offset *vertex* where two segments meet: miter if sharp enough, else bevel."""
    mx, my = n_prev[0] + n_next[0], n_prev[1] + n_next[1]
    length = math.hypot(mx, my)
    bevel = [_shift(vertex, n_prev, distance), _shift(vertex, n_next, distance)]
    if length < _DEGENERATE:        # segments double back: no usable miter
        return bevel
    mdir = (mx / length, my / length)
    cos_half = mdir[0] * n_next[0] + mdir[1] * n_next[1]
    if cos_half < _DEGENERATE or 1.0 / cos_half > miter_limit:
        return bevel
    miter = distance / cos_half     # signed: follows the side of *distance*
    return [(vertex[0] + mdir[0] * miter, vertex[1] + mdir[1] * miter)]


def _left_normal(start: Point, end: Point) -> Point:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    return (-dy / length, dx / length)


def _shift(point: Point, normal: Point, distance: float) -> Point:
    return (point[0] + normal[0] * distance, point[1] + normal[1] * distance)


def _dedupe(points: list[Point]) -> list[Point]:
    out: list[Point] = []
    for point in points:
        if not out or math.hypot(point[0] - out[-1][0], point[1] - out[-1][1]) > _DEGENERATE:
            out.append((float(point[0]), float(point[1])))
    return out
