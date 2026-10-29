"""Cubism ``.motion3.json`` and ``.exp3.json`` importers: flat segment
arrays become :class:`MotionTrack` segments, expression parameters keep
their Cubism blend mode."""
from __future__ import annotations

from pathlib import Path

from Imervue.puppet.cubism_import_common import CubismFormatError, _read_json
from Imervue.puppet.document import (
    Expression,
    ExpressionParam,
    Motion,
    MotionSegment,
    MotionTrack,
)

# Cubism segment-type ids per the v3 spec.
_CUBISM_LINEAR: int = 0
_CUBISM_BEZIER: int = 1
_CUBISM_STEPPED: int = 2
_CUBISM_INVERSE_STEPPED: int = 3

_CUBISM_BLEND_TO_MODE: dict[str, str] = {
    "Add": "additive",
    "Multiply": "multiply",
    "Overwrite": "overwrite",
}


# ---------------------------------------------------------------------------
# .motion3.json
# ---------------------------------------------------------------------------


def load_motion3(path: str | Path, *, name: str | None = None) -> Motion:
    """Parse one Cubism ``.motion3.json`` into our :class:`Motion`.

    ``name`` defaults to the file's stem (``idle_01.motion3.json`` →
    ``idle_01``) so the motion picker in the dock has a readable label.
    Non-``Parameter`` curves (``PartOpacity`` / ``Model``) are skipped —
    they target Cubism-specific state our runtime doesn't model.
    """
    p = Path(path)
    raw = _read_json(p)
    meta = raw.get("Meta") or {}
    motion_name = name or p.stem.removesuffix(".motion3")
    return Motion(
        name=motion_name,
        duration=float(meta.get("Duration", 0.0)),
        loop=bool(meta.get("Loop", False)),
        tracks=_parse_motion_curves(raw.get("Curves") or []),
        fade_in_duration=float(meta.get("FadeInTime", 0.0)),
        fade_out_duration=float(meta.get("FadeOutTime", 0.0)),
    )


def _parse_motion_curves(curves: list[dict]) -> list[MotionTrack]:
    tracks: list[MotionTrack] = []
    for curve in curves:
        if curve.get("Target") != "Parameter":
            continue
        param_id = curve.get("Id")
        segments_raw = curve.get("Segments")
        if not isinstance(param_id, str) or not isinstance(segments_raw, list):
            continue
        tracks.append(
            MotionTrack(
                param_id=param_id,
                segments=_parse_cubism_segments(segments_raw),
            ),
        )
    return tracks


def _parse_cubism_segments(raw: list[float]) -> list[MotionSegment]:
    """Walk Cubism's flat segment array. Format: ``[t0, v0, type, p1,
    p2, ...]`` where each segment consumes a type byte plus 2 (linear /
    stepped / inverse-stepped) or 6 (bezier) floats and the next
    segment continues from the previous segment's endpoint."""
    if len(raw) < 2:
        return []
    cursor = 2
    prev = (float(raw[0]), float(raw[1]))
    segments: list[MotionSegment] = []
    while cursor < len(raw):
        seg_type = int(raw[cursor])
        cursor += 1
        segment, prev, cursor = _consume_segment(raw, cursor, seg_type, prev)
        segments.append(segment)
    return segments


_SEGMENT_FLOATS = {
    _CUBISM_LINEAR: 2,
    _CUBISM_BEZIER: 6,
    _CUBISM_STEPPED: 2,
    _CUBISM_INVERSE_STEPPED: 2,
}


def _consume_segment(
    raw: list[float], cursor: int, seg_type: int, prev: tuple[float, float],
) -> tuple[MotionSegment, tuple[float, float], int]:
    needed = _SEGMENT_FLOATS.get(seg_type)
    if needed is None:
        raise CubismFormatError(f"unknown Cubism segment type {seg_type}")
    if cursor + needed > len(raw):
        # A truncated motion3.json would otherwise raise IndexError from the
        # unchecked raw[cursor + N] reads below, which the importer doesn't catch.
        raise CubismFormatError(
            f"truncated Cubism motion: segment type {seg_type} needs {needed} "
            f"floats at {cursor}, only {len(raw)} present",
        )
    if seg_type == _CUBISM_LINEAR:
        p1 = (float(raw[cursor]), float(raw[cursor + 1]))
        return MotionSegment(type="linear", p0=prev, p1=p1), p1, cursor + 2
    if seg_type == _CUBISM_BEZIER:
        c0 = (float(raw[cursor]), float(raw[cursor + 1]))
        c1 = (float(raw[cursor + 2]), float(raw[cursor + 3]))
        p1 = (float(raw[cursor + 4]), float(raw[cursor + 5]))
        return (
            MotionSegment(type="cubic-bezier", p0=prev, p1=p1, c0=c0, c1=c1),
            p1, cursor + 6,
        )
    if seg_type == _CUBISM_STEPPED:
        p1 = (float(raw[cursor]), float(raw[cursor + 1]))
        return MotionSegment(type="stepped", p0=prev, p1=p1), p1, cursor + 2
    if seg_type == _CUBISM_INVERSE_STEPPED:
        p1 = (float(raw[cursor]), float(raw[cursor + 1]))
        return MotionSegment(type="inverse-stepped", p0=prev, p1=p1), p1, cursor + 2
    raise CubismFormatError(f"unknown Cubism segment type {seg_type}")


# ---------------------------------------------------------------------------
# .exp3.json
# ---------------------------------------------------------------------------


def load_exp3(path: str | Path, *, name: str | None = None) -> Expression:
    """Parse one Cubism ``.exp3.json`` into our :class:`Expression`."""
    p = Path(path)
    raw = _read_json(p)
    if raw.get("Type") not in (None, "Live2D Expression"):
        raise CubismFormatError(
            f"{p} Type {raw.get('Type')!r} is not 'Live2D Expression'",
        )
    expression_name = name or p.stem.removesuffix(".exp3")
    return Expression(
        name=expression_name,
        params=[_parse_exp_param(p) for p in raw.get("Parameters") or []],
    )


def _parse_exp_param(raw: dict) -> ExpressionParam:
    cubism_blend = raw.get("Blend", "Add")
    mode = _CUBISM_BLEND_TO_MODE.get(cubism_blend)
    if mode is None:
        raise CubismFormatError(
            f"unknown Cubism expression Blend {cubism_blend!r}; "
            f"expected one of {list(_CUBISM_BLEND_TO_MODE)}",
        )
    return ExpressionParam(
        id=str(raw["Id"]),
        value=float(raw.get("Value", 0.0)),
        mode=mode,
    )
