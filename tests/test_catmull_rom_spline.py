"""Tests for Catmull-Rom stroke resampling."""
from __future__ import annotations

import pytest

from Imervue.paint.catmull_rom_spline import (
    catmull_rom_point,
    resample_polyline_catmull_rom,
)


# ---------------------------------------------------------------------------
# catmull_rom_point
# ---------------------------------------------------------------------------


def test_endpoints_are_interpolated():
    p0, p1, p2, p3 = (0, 0), (1, 1), (2, 0), (3, 1)
    assert catmull_rom_point(p0, p1, p2, p3, 0.0) == pytest.approx((1, 1))
    assert catmull_rom_point(p0, p1, p2, p3, 1.0) == pytest.approx((2, 0))


def test_collinear_segment_stays_on_line():
    # Evenly spaced collinear points -> midpoint is the geometric midpoint.
    p = [(0, 0), (1, 0), (2, 0), (3, 0)]
    mid = catmull_rom_point(*p, 0.5)
    assert mid == pytest.approx((1.5, 0.0))


# ---------------------------------------------------------------------------
# resample_polyline_catmull_rom
# ---------------------------------------------------------------------------


def test_short_input_unchanged():
    assert resample_polyline_catmull_rom([]) == []
    assert resample_polyline_catmull_rom([(1.0, 2.0)]) == [(1.0, 2.0)]


def test_open_curve_passes_through_vertices():
    pts = [(0, 0), (1, 2), (2, 0)]
    samples = 4
    out = resample_polyline_catmull_rom(pts, samples_per_segment=samples)
    assert out[0] == pytest.approx((0, 0))
    assert out[samples] == pytest.approx((1, 2))   # start of 2nd segment
    assert out[-1] == pytest.approx((2, 0))


def test_open_curve_point_count():
    pts = [(0, 0), (1, 1), (2, 0), (3, 1)]
    samples = 8
    out = resample_polyline_catmull_rom(pts, samples_per_segment=samples)
    assert len(out) == (len(pts) - 1) * samples + 1


def test_closed_curve_point_count():
    pts = [(0, 0), (1, 0), (1, 1), (0, 1)]
    samples = 6
    out = resample_polyline_catmull_rom(pts, closed=True, samples_per_segment=samples)
    assert len(out) == len(pts) * samples


def test_collinear_polyline_stays_collinear():
    pts = [(0, 0), (1, 0), (2, 0), (3, 0)]
    out = resample_polyline_catmull_rom(pts, samples_per_segment=5)
    assert all(y == pytest.approx(0.0) for _, y in out)


def test_two_points_is_a_line():
    out = resample_polyline_catmull_rom([(0, 0), (4, 8)], samples_per_segment=4)
    assert out[0] == pytest.approx((0, 0))
    assert out[-1] == pytest.approx((4, 8))
    # All samples lie on the straight line y = 2x.
    assert all(y == pytest.approx(2 * x) for x, y in out)
