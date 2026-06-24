"""Compress a :class:`Motion`'s tracks by dropping redundant keyframes.

A motion captured from a webcam / drag recorder lands one key per sampled
frame, most of which sit on the straight line between their neighbours. This
module runs Ramer–Douglas–Peucker over each run of ``linear`` segments — using
*vertical* (value-at-time) error since a motion track is a time series — and
rebuilds the run from the surviving keys. Non-linear segments (``stepped`` /
``inverse-stepped`` / ``cubic-bezier``) pass through untouched, and runs are
never merged across them, so the sampled curve stays within ``tol`` of the
original everywhere. Pure data work — no Qt, no numpy.
"""
from __future__ import annotations

from dataclasses import replace
from typing import cast

from Imervue.puppet.document import Motion, MotionSegment, MotionTrack

Point = tuple[float, float]


def count_keys(track: MotionTrack) -> int:
    """Return the number of keyframe points in ``track`` (segments + 1)."""
    return len(track.segments) + 1 if track.segments else 0


def simplify_polyline(points: list[Point], *, tol: float) -> list[Point]:
    """Ramer–Douglas–Peucker on a ``(time, value)`` polyline.

    Keeps the endpoints and every interior point whose value deviates by more
    than ``tol`` from the straight line interpolated at its time. ``tol <= 0``
    or fewer than three points returns a copy unchanged.
    """
    if len(points) <= 2 or tol <= 0:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack: list[tuple[int, int]] = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        index, dmax = _max_vertical_error(points, start, end)
        if dmax > tol:
            keep[index] = True
            stack.append((start, index))
            stack.append((index, end))
    return [point for point, kept in zip(points, keep, strict=True) if kept]


def compress_track(track: MotionTrack, *, tol: float) -> MotionTrack:
    """Return a new track with redundant keys in its linear runs removed."""
    if not track.segments:
        return MotionTrack(track.param_id, [])
    out: list[MotionSegment] = []
    run: list[MotionSegment] = []
    for segment in track.segments:
        if segment.type == "linear":
            run.append(segment)
            continue
        out.extend(_flush_linear_run(run, tol))
        run = []
        out.append(segment)
    out.extend(_flush_linear_run(run, tol))
    return MotionTrack(track.param_id, out)


def compress_motion(motion: Motion, *, tol: float) -> Motion:
    """Return a copy of ``motion`` with every track compressed.

    All non-track fields (duration, loop, fades, sound, group) are preserved.
    """
    tracks = [compress_track(track, tol=tol) for track in motion.tracks]
    # ``replace`` is typed as returning the dataclass type; make it explicit
    # for analysers that don't infer it (Sonar S5886).
    return cast(Motion, replace(motion, tracks=tracks))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flush_linear_run(run: list[MotionSegment], tol: float) -> list[MotionSegment]:
    if len(run) <= 1:
        return list(run)
    points = [run[0].p0, *(segment.p1 for segment in run)]
    simplified = simplify_polyline(points, tol=tol)
    return [
        MotionSegment("linear", simplified[i], simplified[i + 1])
        for i in range(len(simplified) - 1)
    ]


def _line_value(a: Point, b: Point, time_sec: float) -> float:
    t0, v0 = a
    t1, v1 = b
    if t1 == t0:
        return v0
    return v0 + (v1 - v0) * (time_sec - t0) / (t1 - t0)


def _max_vertical_error(
    points: list[Point], start: int, end: int,
) -> tuple[int, float]:
    a, b = points[start], points[end]
    best_index, best_error = start, 0.0
    for i in range(start + 1, end):
        error = abs(points[i][1] - _line_value(a, b, points[i][0]))
        if error > best_error:
            best_error = error
            best_index = i
    return best_index, best_error
