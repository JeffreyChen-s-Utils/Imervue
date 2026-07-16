"""simplify_polyline must handle a long contour without a RecursionError.

The recursive Douglas-Peucker blew Python's ~1000-frame limit on the long,
high-curvature polylines that marching-squares produces for detailed lineart; it
is now iterative.
"""
from __future__ import annotations

from Imervue.paint.image_trace import simplify_polyline


def test_long_high_curvature_contour_does_not_recurse_to_death():
    # A concave (sqrt) curve keeps Douglas-Peucker splits unbalanced, which drove
    # recursion depth well past the frame limit for a long contour.
    polyline = [(float(i), (i ** 0.5) * 500.0) for i in range(5000)]
    result = simplify_polyline(polyline, tolerance=1.0)   # must not raise
    assert result[0] == polyline[0]
    assert result[-1] == polyline[-1]
    assert 2 <= len(result) <= len(polyline)


def test_short_polyline_unchanged():
    line = [(0.0, 0.0), (1.0, 0.0)]
    assert simplify_polyline(line, tolerance=1.0) == line
