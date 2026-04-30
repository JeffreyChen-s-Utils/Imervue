"""Tests for image-trace marching squares + Douglas-Peucker."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.image_trace import (
    find_contours,
    find_segments,
    simplify_polyline,
)


def _square_mask(h=20, w=20, top=4, left=4, side=12):
    m = np.zeros((h, w), dtype=np.bool_)
    m[top:top + side, left:left + side] = True
    return m


def _circle_mask(h=20, w=20, cx=10, cy=10, r=5):
    m = np.zeros((h, w), dtype=np.bool_)
    ys, xs = np.indices((h, w))
    m[(xs - cx) ** 2 + (ys - cy) ** 2 <= r * r] = True
    return m


# ---------------------------------------------------------------------------
# find_segments
# ---------------------------------------------------------------------------


def test_find_segments_empty_mask_returns_empty():
    m = np.zeros((10, 10), dtype=np.bool_)
    assert find_segments(m) == []


def test_find_segments_full_mask_returns_empty():
    m = np.ones((10, 10), dtype=np.bool_)
    # Every cell has all four corners True → no boundary crossings.
    assert find_segments(m) == []


def test_find_segments_square_yields_perimeter_segments():
    m = _square_mask(h=10, w=10, top=3, left=3, side=4)
    segments = find_segments(m)
    # A 4×4 square has 4 sides × 4 segments per side = 16 cells along
    # the boundary, each emitting one segment. Expect ~16.
    assert 12 <= len(segments) <= 20


def test_find_segments_rejects_non_2d():
    bad = np.zeros((10, 10, 4), dtype=np.bool_)
    with pytest.raises(ValueError, match="2-D"):
        find_segments(bad)


def test_find_segments_too_small_returns_empty():
    """A 1×1 mask can't form any 2×2 cells."""
    m = np.array([[True]], dtype=np.bool_)
    assert find_segments(m) == []


# ---------------------------------------------------------------------------
# find_contours
# ---------------------------------------------------------------------------


def test_find_contours_square_returns_single_closed_polyline():
    m = _square_mask(h=10, w=10, top=3, left=3, side=4)
    contours = find_contours(m)
    assert len(contours) >= 1
    # The first contour should be closed (first == last).
    longest = max(contours, key=len)
    assert longest[0] == longest[-1]


def test_find_contours_circle_polyline_long():
    m = _circle_mask(h=20, w=20, cx=10, cy=10, r=5)
    contours = find_contours(m)
    longest = max(contours, key=len)
    # A circle contour should have many points (> 10 — proportional
    # to perimeter).
    assert len(longest) > 10


def test_find_contours_two_components_yields_at_least_two_polylines():
    m = np.zeros((20, 30), dtype=np.bool_)
    m[2:8, 2:8] = True
    m[12:18, 20:28] = True
    contours = find_contours(m)
    assert len(contours) >= 2


def test_find_contours_empty_mask_returns_empty():
    m = np.zeros((10, 10), dtype=np.bool_)
    assert find_contours(m) == []


# ---------------------------------------------------------------------------
# simplify_polyline
# ---------------------------------------------------------------------------


def test_simplify_polyline_straight_line_collapses_to_endpoints():
    """A polyline of collinear points should reduce to just the two
    endpoints."""
    line = [(float(x), 0.0) for x in range(20)]
    out = simplify_polyline(line, tolerance=0.5)
    assert out == [(0.0, 0.0), (19.0, 0.0)]


def test_simplify_polyline_keeps_significant_kink():
    """A line with a sharp 45° turn should keep the corner point."""
    poly = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 5.0), (10.0, 10.0)]
    out = simplify_polyline(poly, tolerance=0.5)
    assert (10.0, 0.0) in out


def test_simplify_polyline_zero_tolerance_returns_input_copy():
    poly = [(0.0, 0.0), (5.0, 5.0), (10.0, 10.0)]
    out = simplify_polyline(poly, tolerance=0.0)
    assert out == poly
    assert out is not poly   # is a copy


def test_simplify_polyline_short_input_returns_copy():
    poly = [(0.0, 0.0), (1.0, 1.0)]
    out = simplify_polyline(poly, tolerance=10.0)
    assert out == poly


def test_simplify_polyline_preserves_endpoints():
    """Whatever the tolerance, the first and last points always
    survive simplification."""
    line = [(float(x), float(x)) for x in range(20)]
    out = simplify_polyline(line, tolerance=100.0)
    assert out[0] == line[0]
    assert out[-1] == line[-1]
