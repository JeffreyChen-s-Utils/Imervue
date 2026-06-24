"""Tests for motion track keyframe compression."""
from __future__ import annotations

import pytest

from Imervue.puppet.document import Motion, MotionSegment, MotionTrack
from Imervue.puppet.motion_compress import (
    compress_motion,
    compress_track,
    count_keys,
    simplify_polyline,
)
from Imervue.puppet.motion_sampler import sample_track


def _linear_track(points, param_id="ParamAngleX"):
    segments = [
        MotionSegment("linear", points[i], points[i + 1])
        for i in range(len(points) - 1)
    ]
    return MotionTrack(param_id, segments)


# ---------------------------------------------------------------------------
# simplify_polyline
# ---------------------------------------------------------------------------


def test_simplify_collinear_reduces_to_endpoints():
    points = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
    assert simplify_polyline(points, tol=0.01) == [(0.0, 0.0), (3.0, 3.0)]


def test_simplify_keeps_significant_peak():
    points = [(0.0, 0.0), (1.0, 0.5), (2.0, 0.0)]
    assert simplify_polyline(points, tol=0.1) == points


def test_simplify_drops_peak_below_tolerance():
    points = [(0.0, 0.0), (1.0, 0.05), (2.0, 0.0)]
    assert simplify_polyline(points, tol=0.1) == [(0.0, 0.0), (2.0, 0.0)]


def test_simplify_tol_zero_keeps_all():
    points = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]
    assert simplify_polyline(points, tol=0.0) == points


def test_simplify_two_points_unchanged():
    assert simplify_polyline([(0.0, 0.0), (1.0, 1.0)], tol=0.5) == [
        (0.0, 0.0), (1.0, 1.0)]


# ---------------------------------------------------------------------------
# count_keys
# ---------------------------------------------------------------------------


def test_count_keys_empty_and_nonempty():
    assert count_keys(MotionTrack("p", [])) == 0
    track = _linear_track([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
    assert count_keys(track) == 3


# ---------------------------------------------------------------------------
# compress_track
# ---------------------------------------------------------------------------


def test_compress_collinear_run_to_single_segment():
    track = _linear_track([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)])
    out = compress_track(track, tol=0.01)
    assert count_keys(out) == 2
    assert out.segments[0].p0 == (0.0, 0.0)
    assert out.segments[0].p1 == (3.0, 3.0)


def test_compress_empty_track():
    out = compress_track(MotionTrack("p", []), tol=0.1)
    assert out.segments == []


def test_compress_single_segment_unchanged():
    track = _linear_track([(0.0, 0.0), (1.0, 1.0)])
    out = compress_track(track, tol=0.1)
    assert count_keys(out) == 2


def test_compress_preserves_non_linear_and_does_not_cross_it():
    # Two collinear linear segments, a stepped segment, then two more collinear.
    track = MotionTrack("p", [
        MotionSegment("linear", (0.0, 0.0), (1.0, 1.0)),
        MotionSegment("linear", (1.0, 1.0), (2.0, 2.0)),
        MotionSegment("stepped", (2.0, 2.0), (3.0, 5.0)),
        MotionSegment("linear", (3.0, 5.0), (4.0, 6.0)),
        MotionSegment("linear", (4.0, 6.0), (5.0, 7.0)),
    ])
    out = compress_track(track, tol=0.01)
    types = [s.type for s in out.segments]
    assert types == ["linear", "stepped", "linear"]
    assert out.segments[1].type == "stepped"


def test_compress_keeps_real_keys():
    # A genuine corner at (1, 1) must survive.
    track = _linear_track([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)])
    out = compress_track(track, tol=0.01)
    assert count_keys(out) == 3


# ---------------------------------------------------------------------------
# compress_motion
# ---------------------------------------------------------------------------


def test_compress_motion_preserves_metadata():
    track = _linear_track([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
    motion = Motion("Idle", duration=2.0, loop=True, tracks=[track],
                    fade_in_duration=0.3, group="Idle")
    out = compress_motion(motion, tol=0.01)
    assert out.duration == pytest.approx(2.0)
    assert out.loop is True
    assert out.fade_in_duration == pytest.approx(0.3)
    assert out.group == "Idle"
    assert count_keys(out.tracks[0]) == 2


def test_compress_motion_does_not_mutate_original():
    track = _linear_track([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
    motion = Motion("Idle", duration=2.0, tracks=[track])
    compress_motion(motion, tol=0.01)
    assert count_keys(motion.tracks[0]) == 3


def test_compressed_track_samples_within_tolerance():
    # A ramp with small sub-tolerance wiggles riding on it: compression should
    # drop the wiggle keys yet keep sampling within tol of the original.
    wiggle = 0.02
    points = [
        (i * 0.1, i * 0.1 + (wiggle if i % 2 else -wiggle))
        for i in range(11)
    ]
    track = _linear_track(points)
    tol = 0.05
    out = compress_track(track, tol=tol)
    assert count_keys(out) < count_keys(track)
    for step in range(101):
        t = step * 0.01
        assert abs(sample_track(track, t) - sample_track(out, t)) <= tol + 1e-9
