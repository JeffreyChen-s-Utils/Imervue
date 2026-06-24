"""Tests for the polyline offset (parallel curve)."""
from __future__ import annotations

import math

import pytest

from Imervue.paint.polyline_offset import offset_polyline


def _close(a, b, tol=1e-6):
    return math.isclose(a[0], b[0], abs_tol=tol) and math.isclose(a[1], b[1], abs_tol=tol)


def test_straight_segment_shifts_by_normal():
    out = offset_polyline([(0.0, 0.0), (10.0, 0.0)], distance=2.0)
    assert _close(out[0], (0.0, 2.0))
    assert _close(out[1], (10.0, 2.0))


def test_negative_distance_offsets_other_side():
    out = offset_polyline([(0.0, 0.0), (10.0, 0.0)], distance=-2.0)
    assert _close(out[0], (0.0, -2.0))
    assert _close(out[1], (10.0, -2.0))


def test_right_angle_miter_join():
    out = offset_polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], distance=2.0)
    # Offset lines y=2 and x=8 intersect at the mitered corner (8, 2).
    assert len(out) == 3
    assert _close(out[1], (8.0, 2.0))


def test_collinear_points_stay_parallel():
    out = offset_polyline([(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)], distance=3.0)
    assert all(_close((0.0, p[1]), (0.0, 3.0)) for p in out)


def test_sharp_corner_bevels_into_two_points():
    # A near-spike corner exceeds the miter limit -> the vertex becomes a bevel.
    spike = [(0.0, 0.0), (10.0, 0.0), (0.0, 0.3)]
    out = offset_polyline(spike, distance=1.0, miter_limit=2.0)
    assert len(out) == 4  # 2 endpoints + 2 bevel points at the corner


def test_high_miter_limit_keeps_single_point():
    spike = [(0.0, 0.0), (10.0, 0.0), (0.0, 0.3)]
    out = offset_polyline(spike, distance=1.0, miter_limit=100.0)
    assert len(out) == 3  # miter accepted -> one corner point


def test_collapses_duplicate_points():
    out = offset_polyline([(0.0, 0.0), (0.0, 0.0), (10.0, 0.0)], distance=1.0)
    assert len(out) == 2


def test_offset_distance_is_preserved_on_straight_line():
    pts = [(1.0, 1.0), (4.0, 5.0)]  # arbitrary direction
    out = offset_polyline(pts, distance=2.5)
    # Each endpoint sits exactly 2.5 away, perpendicular to the segment.
    assert math.isclose(math.dist(out[0], pts[0]), 2.5, abs_tol=1e-6)
    assert math.isclose(math.dist(out[1], pts[1]), 2.5, abs_tol=1e-6)


def test_rejects_single_point():
    with pytest.raises(ValueError, match="at least two"):
        offset_polyline([(0.0, 0.0)], distance=1.0)


def test_rejects_all_duplicate_points():
    with pytest.raises(ValueError, match="at least two"):
        offset_polyline([(3.0, 3.0), (3.0, 3.0)], distance=1.0)


def test_does_not_mutate_input():
    pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    before = list(pts)
    offset_polyline(pts, distance=2.0)
    assert pts == before
