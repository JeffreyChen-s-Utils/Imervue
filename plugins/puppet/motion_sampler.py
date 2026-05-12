"""Pure-Python motion sampling — given a :class:`Motion` and a time
in seconds, return the parameter values for every track on that
motion.

Curve segment math implements the four `.puppet` v1 segment types:
``linear``, ``stepped``, ``inverse-stepped``, ``cubic-bezier``.
Looping is just a modulo over ``Motion.duration``; the player module
on top of this handles the QTimer wiring.
"""
from __future__ import annotations

from puppet.document import Motion, MotionSegment, MotionTrack


def sample_motion(
    motion: Motion, time_sec: float, *, loop: bool | None = None,
) -> dict[str, float]:
    """Return ``{param_id: value}`` sampled at ``time_sec``.

    ``loop`` overrides ``motion.loop`` if given — useful for the
    player UI to flip looping without mutating the document.
    """
    duration = max(0.0, float(motion.duration))
    use_loop = motion.loop if loop is None else loop
    if duration <= 0.0:
        return {t.param_id: _track_initial_value(t) for t in motion.tracks}

    t = (
        float(time_sec) % duration if use_loop
        else max(0.0, min(duration, float(time_sec)))
    )

    return {track.param_id: sample_track(track, t) for track in motion.tracks}


def sample_track(track: MotionTrack, time_sec: float) -> float:
    """Return the parameter value for ``track`` at ``time_sec``."""
    if not track.segments:
        return 0.0
    # Clamp before all segments
    if time_sec <= track.segments[0].p0[0]:
        return float(track.segments[0].p0[1])
    # Pick the matching segment
    for segment in track.segments:
        t0 = segment.p0[0]
        t1 = segment.p1[0]
        if t0 <= time_sec <= t1:
            return _sample_segment(segment, time_sec)
    # Past all segments → final value
    return float(track.segments[-1].p1[1])


def _sample_segment(segment: MotionSegment, time_sec: float) -> float:
    t0, v0 = segment.p0
    t1, v1 = segment.p1
    if t1 <= t0:
        return float(v0)
    u = (time_sec - t0) / (t1 - t0)
    if segment.type == "linear":
        return float(v0 + (v1 - v0) * u)
    if segment.type == "stepped":
        return float(v0)
    if segment.type == "inverse-stepped":
        return float(v1)
    if segment.type == "cubic-bezier":
        return _cubic_bezier_value(segment, time_sec)
    return float(v0)


def _cubic_bezier_value(segment: MotionSegment, time_sec: float) -> float:
    """Sample a cubic-bezier segment (motion3-style: time-vs-value)
    where the segment carries two extra control points ``c0`` / ``c1``.

    Solves the time → bezier-parameter mapping numerically (5 Newton
    iterations is plenty for sub-millisecond accuracy across realistic
    motion lengths).
    """
    t0, v0 = segment.p0
    t1, v1 = segment.p1
    if segment.c0 is None or segment.c1 is None:
        u = (time_sec - t0) / (t1 - t0)
        return float(v0 + (v1 - v0) * u)
    c0t, c0v = segment.c0
    c1t, c1v = segment.c1
    u = _bezier_param_for_time(time_sec, t0, c0t, c1t, t1)
    return float(_bezier_eval(u, v0, c0v, c1v, v1))


def _bezier_eval(u: float, p0: float, p1: float, p2: float, p3: float) -> float:
    one_minus = 1.0 - u
    return (
        one_minus ** 3 * p0
        + 3.0 * one_minus ** 2 * u * p1
        + 3.0 * one_minus * u ** 2 * p2
        + u ** 3 * p3
    )


def _bezier_param_for_time(
    time_sec: float, t0: float, c0t: float, c1t: float, t1: float,
) -> float:
    """Newton-step the parameter ``u`` so that
    ``bezier(u, t0, c0t, c1t, t1) ≈ time_sec``."""
    span = t1 - t0
    if span <= 0:
        return 0.0
    u = (time_sec - t0) / span
    for _ in range(5):
        x = _bezier_eval(u, t0, c0t, c1t, t1)
        dx = _bezier_derivative(u, t0, c0t, c1t, t1)
        if dx == 0:
            break
        u -= (x - time_sec) / dx
        u = max(0.0, min(1.0, u))
    return u


def _bezier_derivative(u: float, p0: float, p1: float, p2: float, p3: float) -> float:
    one_minus = 1.0 - u
    return (
        3.0 * one_minus ** 2 * (p1 - p0)
        + 6.0 * one_minus * u * (p2 - p1)
        + 3.0 * u ** 2 * (p3 - p2)
    )


def _track_initial_value(track: MotionTrack) -> float:
    if not track.segments:
        return 0.0
    return float(track.segments[0].p0[1])


# ---------------------------------------------------------------------------
# Convenience: validate a motion's tracks tile the timeline without gaps
# ---------------------------------------------------------------------------


def find_motion_gaps(motion: Motion) -> list[tuple[str, float, float]]:
    """Return ``(param_id, gap_start, gap_end)`` tuples for any track
    where consecutive segments don't tile contiguously. Tests use this
    to assert authored motions are well-formed.
    """
    gaps: list[tuple[str, float, float]] = []
    for track in motion.tracks:
        for prev, nxt in zip(track.segments, track.segments[1:], strict=False):
            if abs(prev.p1[0] - nxt.p0[0]) > 1e-6:
                gaps.append((track.param_id, prev.p1[0], nxt.p0[0]))
    return gaps
