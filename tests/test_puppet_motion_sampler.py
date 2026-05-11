"""Tests for the curve sampler (linear / stepped / inverse-stepped /
cubic-bezier) and the motion-level sample_motion entry point.
"""
from __future__ import annotations

import pytest

from Imervue.puppet.document import Motion, MotionSegment, MotionTrack
from Imervue.puppet.motion_sampler import (
    find_motion_gaps,
    sample_motion,
    sample_track,
)


def _track(*segments: MotionSegment, param: str = "X") -> MotionTrack:
    return MotionTrack(param_id=param, segments=list(segments))


def _linear(t0: float, v0: float, t1: float, v1: float) -> MotionSegment:
    return MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1))


# ---------------------------------------------------------------------------
# sample_track segment math
# ---------------------------------------------------------------------------


def test_linear_interpolates_between_endpoints():
    track = _track(_linear(0.0, 0.0, 1.0, 10.0))
    assert sample_track(track, 0.0) == pytest.approx(0.0)
    assert sample_track(track, 0.5) == pytest.approx(5.0)
    assert sample_track(track, 1.0) == pytest.approx(10.0)


def test_stepped_holds_p0_value_for_full_span():
    track = _track(MotionSegment(type="stepped", p0=(0.0, 7.0), p1=(1.0, 99.0)))
    assert sample_track(track, 0.0) == pytest.approx(7.0)
    assert sample_track(track, 0.99) == pytest.approx(7.0)
    # At t1 the next-segment lookup picks up p1
    assert sample_track(track, 1.0) == pytest.approx(7.0)


def test_inverse_stepped_holds_p1_value_for_full_span():
    track = _track(MotionSegment(type="inverse-stepped", p0=(0.0, 7.0), p1=(1.0, 42.0)))
    assert sample_track(track, 0.01) == pytest.approx(42.0)
    assert sample_track(track, 0.99) == pytest.approx(42.0)


def test_cubic_bezier_hits_endpoints_exactly():
    seg = MotionSegment(
        type="cubic-bezier",
        p0=(0.0, 0.0), c0=(0.3, 0.0), c1=(0.7, 1.0), p1=(1.0, 1.0),
    )
    track = _track(seg)
    assert sample_track(track, 0.0) == pytest.approx(0.0, abs=1e-3)
    assert sample_track(track, 1.0) == pytest.approx(1.0, abs=1e-3)


def test_cubic_bezier_monotone_for_monotone_handles():
    seg = MotionSegment(
        type="cubic-bezier",
        p0=(0.0, 0.0), c0=(0.25, 0.5), c1=(0.75, 0.5), p1=(1.0, 1.0),
    )
    track = _track(seg)
    samples = [sample_track(track, t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    # Output should be monotone increasing
    for prev, nxt in zip(samples, samples[1:], strict=False):
        assert nxt >= prev - 1e-6


def test_clamp_before_first_segment():
    track = _track(_linear(1.0, 5.0, 2.0, 10.0))
    # Sampling before any segment returns the first p0 value
    assert sample_track(track, 0.0) == pytest.approx(5.0)


def test_clamp_after_last_segment():
    track = _track(_linear(0.0, 0.0, 1.0, 10.0))
    assert sample_track(track, 5.0) == pytest.approx(10.0)


def test_segments_chain_for_multi_segment_track():
    track = _track(
        _linear(0.0, 0.0, 1.0, 10.0),
        _linear(1.0, 10.0, 2.0, 0.0),
    )
    assert sample_track(track, 0.5) == pytest.approx(5.0)
    assert sample_track(track, 1.5) == pytest.approx(5.0)


def test_zero_duration_segment_returns_p0():
    track = _track(MotionSegment(type="linear", p0=(1.0, 9.0), p1=(1.0, 10.0)))
    assert sample_track(track, 1.0) == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# sample_motion (full motion + looping)
# ---------------------------------------------------------------------------


def _idle_motion(loop: bool = True) -> Motion:
    return Motion(
        name="idle",
        duration=2.0,
        loop=loop,
        tracks=[
            _track(_linear(0.0, 0.0, 1.0, 1.0), _linear(1.0, 1.0, 2.0, 0.0)),
        ],
    )


def test_sample_motion_clamps_when_not_looping():
    m = _idle_motion(loop=False)
    assert sample_motion(m, 5.0)["X"] == pytest.approx(0.0)


def test_sample_motion_wraps_when_looping():
    m = _idle_motion(loop=True)
    # 2.0 + 0.5 == loops back to 0.5 → linear → 0.5
    assert sample_motion(m, 2.5)["X"] == pytest.approx(0.5)


def test_sample_motion_loop_argument_overrides_motion_loop():
    m = _idle_motion(loop=False)
    assert sample_motion(m, 2.5, loop=True)["X"] == pytest.approx(0.5)


def test_sample_motion_with_zero_duration_returns_initial_values():
    m = Motion(name="zero", duration=0.0, loop=False, tracks=[
        _track(_linear(0.0, 7.0, 1.0, 9.0)),
    ])
    assert sample_motion(m, 0.5)["X"] == pytest.approx(7.0)


def test_sample_motion_handles_empty_track():
    m = Motion(name="empty", duration=1.0, loop=False, tracks=[
        MotionTrack(param_id="X", segments=[]),
    ])
    assert sample_motion(m, 0.5)["X"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# find_motion_gaps
# ---------------------------------------------------------------------------


def test_find_motion_gaps_clean_track_returns_empty():
    m = _idle_motion()
    assert find_motion_gaps(m) == []


def test_find_motion_gaps_reports_disjoint_segments():
    m = Motion(name="bad", duration=2.0, loop=False, tracks=[
        _track(_linear(0.0, 0.0, 0.5, 1.0), _linear(1.0, 1.0, 1.5, 2.0)),
    ])
    gaps = find_motion_gaps(m)
    assert gaps == [("X", 0.5, 1.0)]
