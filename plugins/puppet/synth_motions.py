"""Synthesise a small set of idle-style motions for converted rigs.

Cubism exports often ship few or zero ``.motion3.json`` files — the
March 7th drop is one such bundle. The rig itself supports plenty of
parameters (``ParamAngleX``, ``ParamBreath``, eye-open pairs, …) but
without authored motions the user has nothing to play back.

These helpers build a handful of pure-linear loops that touch only the
parameters the document actually declares, so the workspace's motion
list isn't empty after a Cubism conversion. The motions are clearly
labelled ``synth/*`` so an author can delete them if they later record
real ones, and they default to ``group="Idle"`` so the motion dock's
filter buckets them together with imported idle loops.

The module is Qt-free / numpy-free so the converter can call into it
without dragging GUI deps into the import pipeline."""
from __future__ import annotations

from puppet.document import (
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    PuppetDocument,
)
from puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Y,
    PARAM_ANGLE_Z,
    PARAM_BODY_ANGLE_X,
    PARAM_BODY_ANGLE_Z,
    PARAM_BREATH,
    PARAM_EYE_L_OPEN,
    PARAM_EYE_R_OPEN,
)

_SYNTH_NAME_PREFIX: str = "synth"
_DEFAULT_FADE_S: float = 0.5
_MIN_AMPLITUDE_FRACTION: float = 0.6
"""Synth motions sweep this fraction of each parameter's range. ``0.6``
gives a clearly-visible motion without slamming every parameter to its
authored extreme (which on many rigs looks broken)."""


def synthesise_idle_motions(document: PuppetDocument) -> list[Motion]:
    """Build the synth motion set for ``document``.

    Each motion is included only when at least one of its target
    parameters exists on the document. Motions targeting no available
    parameters are dropped so the user doesn't see empty placeholder
    entries in the motion picker.

    Pure function — caller appends the result to the document's motion
    list. Tests inspect the result directly without touching Qt."""
    params_by_id = {p.id: p for p in document.parameters}
    motions: list[Motion] = []
    head_sway = _build_head_sway(params_by_id)
    if head_sway is not None:
        motions.append(head_sway)
    blink = _build_blink(params_by_id)
    if blink is not None:
        motions.append(blink)
    body_lean = _build_body_lean(params_by_id)
    if body_lean is not None:
        motions.append(body_lean)
    breath = _build_breath(params_by_id)
    if breath is not None:
        motions.append(breath)
    return motions


# ---------------------------------------------------------------------------
# Individual motion builders
# ---------------------------------------------------------------------------


def _build_head_sway(params: dict[str, Parameter]) -> Motion | None:
    """Side-to-side head sweep — flat 4-second loop sweeping
    ``ParamAngleX`` neutral → +amp → -amp → neutral.

    Also drives ``ParamAngleZ`` with a quarter-phase tilt so the head
    feels like it's pivoting rather than rigidly translating, and a
    half-amplitude ``ParamAngleY`` track when present so the nod axis
    doesn't sit completely frozen."""
    tracks: list[MotionTrack] = []
    duration = 4.0
    _maybe_add_peak_track(tracks, params, PARAM_ANGLE_X, duration)
    _maybe_add_peak_track(
        tracks, params, PARAM_ANGLE_Z, duration,
        amplitude_fraction=_MIN_AMPLITUDE_FRACTION * 0.6,
        phase=0.25,
    )
    _maybe_add_peak_track(
        tracks, params, PARAM_ANGLE_Y, duration,
        amplitude_fraction=_MIN_AMPLITUDE_FRACTION * 0.5,
        phase=0.5,
    )
    if not tracks:
        return None
    return _wrap_motion("head_sway", duration, tracks)


def _build_blink(params: dict[str, Parameter]) -> Motion | None:
    """Two-blink 3-second loop sharing one curve across both eye
    parameters. Both eyes blink in sync, matching how human eyelids
    behave at rest."""
    duration = 3.0
    tracks: list[MotionTrack] = []
    for eye_param in (PARAM_EYE_L_OPEN, PARAM_EYE_R_OPEN):
        parameter = params.get(eye_param)
        if parameter is None:
            continue
        tracks.append(MotionTrack(
            param_id=parameter.id,
            segments=_blink_segments(parameter, duration),
        ))
    if not tracks:
        return None
    return _wrap_motion("blink", duration, tracks)


def _build_body_lean(params: dict[str, Parameter]) -> Motion | None:
    """Slow 6-second body sway: ``ParamBodyAngleX`` left/right with a
    decorrelated ``ParamBodyAngleZ`` tilt. Reads as relaxed weight
    shifts rather than a metronome."""
    duration = 6.0
    tracks: list[MotionTrack] = []
    _maybe_add_peak_track(
        tracks, params, PARAM_BODY_ANGLE_X, duration,
        amplitude_fraction=_MIN_AMPLITUDE_FRACTION * 0.7,
    )
    _maybe_add_peak_track(
        tracks, params, PARAM_BODY_ANGLE_Z, duration,
        amplitude_fraction=_MIN_AMPLITUDE_FRACTION * 0.4,
        phase=0.25,
    )
    if not tracks:
        return None
    return _wrap_motion("body_lean", duration, tracks)


def _build_breath(params: dict[str, Parameter]) -> Motion | None:
    """Single ``ParamBreath`` rise + fall over 3.5s — matches the
    breath driver's curve so an author who'd rather drive breath off
    the motion timeline gets a representative loop."""
    parameter = params.get(PARAM_BREATH)
    if parameter is None:
        return None
    duration = 3.5
    mid = (parameter.min + parameter.max) / 2.0
    track = MotionTrack(
        param_id=parameter.id,
        segments=[
            MotionSegment(type="linear",
                          p0=(0.0, mid), p1=(duration / 2.0, parameter.max)),
            MotionSegment(type="linear",
                          p0=(duration / 2.0, parameter.max),
                          p1=(duration, mid)),
        ],
    )
    return _wrap_motion("breath", duration, [track])


# ---------------------------------------------------------------------------
# Segment builders
# ---------------------------------------------------------------------------


def _maybe_add_peak_track(
    tracks: list[MotionTrack],
    params: dict[str, Parameter],
    param_id: str,
    duration: float,
    *,
    amplitude_fraction: float = _MIN_AMPLITUDE_FRACTION,
    phase: float = 0.0,
) -> None:
    """Append a four-segment +amp / -amp / neutral peak track when
    ``param_id`` exists on the document.

    ``phase`` shifts the curve by a fraction of one period so multiple
    tracks in the same motion don't move in lockstep."""
    parameter = params.get(param_id)
    if parameter is None:
        return
    segments = _peak_segments(
        parameter, duration,
        amplitude_fraction=amplitude_fraction,
        phase=phase,
    )
    if segments:
        tracks.append(MotionTrack(param_id=parameter.id, segments=segments))


def _peak_segments(
    parameter: Parameter,
    duration: float,
    *,
    amplitude_fraction: float,
    phase: float,
) -> list[MotionSegment]:
    """Four linear segments tracing default → +amp → default → -amp →
    default over ``duration``, optionally rotated by ``phase`` (a
    fraction of one cycle, ``[0, 1)``)."""
    if duration <= 0.0:
        return []
    span_up = parameter.max - parameter.default
    span_down = parameter.default - parameter.min
    if span_up <= 0 and span_down <= 0:
        return []
    high = parameter.default + amplitude_fraction * span_up
    low = parameter.default - amplitude_fraction * span_down
    waypoints = (parameter.default, high, parameter.default, low, parameter.default)
    times = [duration * i / 4.0 for i in range(5)]
    phase_offset = (phase % 1.0) * duration
    times = [(t + phase_offset) % duration for t in times]
    # After phase rotation the waypoints may wrap around; rebuild a
    # legal monotonic timeline by sorting and pairing.
    pairs = sorted(zip(times, waypoints))
    if pairs[0][0] > 0.0:
        pairs.insert(0, (0.0, pairs[-1][1]))
    if pairs[-1][0] < duration:
        pairs.append((duration, pairs[0][1]))
    segments: list[MotionSegment] = []
    for (t0, v0), (t1, v1) in zip(pairs, pairs[1:]):
        if t1 <= t0:
            continue
        segments.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return segments


def _blink_segments(parameter: Parameter, duration: float) -> list[MotionSegment]:
    """Two blinks evenly spaced across ``duration``. Each blink is a
    ~0.18s close + ~0.18s reopen — close to a natural human cadence."""
    open_value = parameter.max
    closed_value = parameter.min
    blink_half = 0.18
    blink_centers = (duration * 0.30, duration * 0.75)
    segments: list[MotionSegment] = []
    cursor = 0.0
    for center in blink_centers:
        close_start = max(cursor, center - blink_half)
        reopen_end = min(duration, center + blink_half)
        if close_start <= cursor:
            close_start = cursor + 0.01
        if reopen_end <= close_start:
            continue
        if close_start > cursor:
            segments.append(MotionSegment(
                type="linear",
                p0=(cursor, open_value), p1=(close_start, open_value),
            ))
        mid = (close_start + reopen_end) / 2.0
        segments.append(MotionSegment(
            type="linear",
            p0=(close_start, open_value), p1=(mid, closed_value),
        ))
        segments.append(MotionSegment(
            type="linear",
            p0=(mid, closed_value), p1=(reopen_end, open_value),
        ))
        cursor = reopen_end
    if cursor < duration:
        segments.append(MotionSegment(
            type="linear",
            p0=(cursor, open_value), p1=(duration, open_value),
        ))
    return segments


# ---------------------------------------------------------------------------
# Wrapping helpers
# ---------------------------------------------------------------------------


def _wrap_motion(suffix: str, duration: float, tracks: list[MotionTrack]) -> Motion:
    motion = Motion(
        name=f"{_SYNTH_NAME_PREFIX}_{suffix}",
        duration=duration,
        loop=True,
        tracks=list(tracks),
        fade_in_duration=_DEFAULT_FADE_S,
        fade_out_duration=_DEFAULT_FADE_S,
    )
    motion.group = "Idle"
    return motion
