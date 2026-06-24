"""Catmull-Rom spline resampling for smooth strokes.

Linear interpolation between raw pen samples leaves visible corners; a uniform
Catmull-Rom spline passes *through* every input point yet curves smoothly
between them — a different trade-off from ``line_cleanup``'s Chaikin smoothing
(which cuts corners) and ``bezier_path`` (which needs authored handles). Pure
coordinate maths on ``(x, y)`` tuples — no Qt, no numpy.

Basis coefficients are the standard uniform Catmull-Rom:
https://en.wikipedia.org/wiki/Centripetal_Catmull%E2%80%93Rom_spline
"""
from __future__ import annotations

from collections.abc import Sequence

Point = tuple[float, float]

# Uniform Catmull-Rom basis constants.
_HALF = 0.5
_TWO = 2.0
_THREE = 3.0
_FOUR = 4.0
_FIVE = 5.0


def _component(a: float, b: float, c: float, d: float, t: float) -> float:
    t2 = t * t
    t3 = t2 * t
    return _HALF * (
        _TWO * b
        + (-a + c) * t
        + (_TWO * a - _FIVE * b + _FOUR * c - d) * t2
        + (-a + _THREE * b - _THREE * c + d) * t3
    )


def catmull_rom_point(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
    """Evaluate the uniform Catmull-Rom segment ``p1 -> p2`` at ``t`` in ``[0, 1]``.

    ``p0`` / ``p3`` are the neighbouring control points. ``t = 0`` returns
    ``p1`` and ``t = 1`` returns ``p2`` (the curve interpolates its endpoints).
    """
    return (
        _component(p0[0], p1[0], p2[0], p3[0], t),
        _component(p0[1], p1[1], p2[1], p3[1], t),
    )


def _control(points: Sequence[Point], index: int, *, closed: bool) -> Point:
    n = len(points)
    if closed:
        return points[index % n]
    return points[min(max(index, 0), n - 1)]


def resample_polyline_catmull_rom(
    points: Sequence[Point], *, closed: bool = False, samples_per_segment: int = 8,
) -> list[Point]:
    """Resample a polyline into a smooth Catmull-Rom curve through its points.

    Each segment is sampled ``samples_per_segment`` times. Open curves clamp the
    end tangents and keep the exact first / last vertex; closed curves wrap. A
    polyline of fewer than two points is returned unchanged.
    """
    pts: list[Point] = [(float(x), float(y)) for x, y in points]
    if len(pts) < 2:
        return pts
    samples = max(1, int(samples_per_segment))
    segment_count = len(pts) if closed else len(pts) - 1
    out: list[Point] = []
    for i in range(segment_count):
        p0 = _control(pts, i - 1, closed=closed)
        p1 = _control(pts, i, closed=closed)
        p2 = _control(pts, i + 1, closed=closed)
        p3 = _control(pts, i + 2, closed=closed)
        for step in range(samples):
            out.append(catmull_rom_point(p0, p1, p2, p3, step / samples))
    if not closed:
        out.append(pts[-1])
    return out
