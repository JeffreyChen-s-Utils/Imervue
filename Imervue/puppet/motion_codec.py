"""Motion tracks, segment geometry and motion-file JSON representation."""
from __future__ import annotations

from Imervue.puppet.document import (
    SCHEMA_VERSION,
    SEGMENT_TYPES,
    Motion,
    MotionSegment,
    MotionTrack,
)
from Imervue.puppet.format_schema import SCHEMA_FIELD, SCHEMA_URLS
from Imervue.puppet.format_values import PuppetFormatError, _dumps, _require_keys, _xy


def _parse_motion(name: str, raw: dict) -> Motion:
    _require_keys(raw, ("duration", "tracks"), f"motion {name}")
    return Motion(
        name=name,
        duration=float(raw["duration"]),
        loop=bool(raw.get("loop", False)),
        tracks=[_parse_track(t) for t in raw["tracks"]],
        fade_in_duration=float(raw.get("fade_in_duration", 0.0)),
        fade_out_duration=float(raw.get("fade_out_duration", 0.0)),
        sound_path=raw.get("sound_path"),
        group=raw.get("group"),
    )


def _parse_track(raw: dict) -> MotionTrack:
    _require_keys(raw, ("param_id", "segments"), "motion track")
    return MotionTrack(
        param_id=str(raw["param_id"]),
        segments=[_parse_segment(s) for s in raw["segments"]],
    )


def _parse_segment(raw: dict) -> MotionSegment:
    seg_type = raw.get("type")
    if seg_type not in SEGMENT_TYPES:
        raise PuppetFormatError(f"segment type {seg_type!r} not in {SEGMENT_TYPES}")
    return MotionSegment(
        type=seg_type,
        p0=_xy(raw["p0"]),
        p1=_xy(raw["p1"]),
        c0=_xy(raw["c0"]) if "c0" in raw else None,
        c1=_xy(raw["c1"]) if "c1" in raw else None,
    )


def _motion_json_bytes(motion: Motion) -> bytes:
    payload = {
        SCHEMA_FIELD: SCHEMA_URLS["motion"],
        "version": SCHEMA_VERSION,
        "duration": motion.duration,
        "loop": motion.loop,
        "tracks": [
            {
                "param_id": t.param_id,
                "segments": [_segment_to_json(s) for s in t.segments],
            }
            for t in motion.tracks
        ],
    }
    if motion.fade_in_duration > 0.0:
        payload["fade_in_duration"] = motion.fade_in_duration
    if motion.fade_out_duration > 0.0:
        payload["fade_out_duration"] = motion.fade_out_duration
    if motion.sound_path:
        payload["sound_path"] = motion.sound_path
    if motion.group:
        payload["group"] = motion.group
    return _dumps(payload)


def _segment_to_json(s: MotionSegment) -> dict:
    out: dict = {
        "type": s.type,
        "p0": list(s.p0),
        "p1": list(s.p1),
    }
    if s.c0 is not None:
        out["c0"] = list(s.c0)
    if s.c1 is not None:
        out["c1"] = list(s.c1)
    return out
