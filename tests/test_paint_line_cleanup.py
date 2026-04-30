"""Tests for line-cleanup helpers (Chaikin smoothing + gap closing)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from Imervue.paint.line_cleanup import (
    CHAIKIN_DEFAULT_ITERATIONS,
    CHAIKIN_MAX_ITERATIONS,
    GAP_CLOSE_MAX,
    close_small_gaps,
    smooth_polyline,
)


# ---------------------------------------------------------------------------
# Chaikin smoothing
# ---------------------------------------------------------------------------


def test_smooth_zero_iterations_returns_copy():
    """Zero iterations is a passthrough — but the result must be a
    fresh list rather than the input alias so callers can mutate it."""
    src = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]
    out = smooth_polyline(src, iterations=0)
    assert out == src
    assert out is not src


def test_smooth_short_polyline_passes_through():
    """A 2-point polyline has no corners to cut — the algorithm must
    return the input rather than vanishing it."""
    src = [(0.0, 0.0), (10.0, 0.0)]
    assert smooth_polyline(src, iterations=4) == src


def test_smooth_empty_polyline_returns_empty():
    assert smooth_polyline([], iterations=4) == []


def test_smooth_doubles_segment_count_per_iteration():
    """Open polyline of N points → 2(N-1) + 2 ≈ 2N points after one
    Chaikin pass. We verify the rough doubling here."""
    src = [(float(i), 0.0) for i in range(5)]
    one = smooth_polyline(src, iterations=1)
    assert len(one) >= 2 * len(src) - 1


def test_smooth_rounds_a_sharp_corner():
    """A right-angle polyline has a maximum y of 0 at the corner;
    after smoothing the corner shifts inward by ≥ 0.25 units."""
    corner = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
    smoothed = smooth_polyline(corner, iterations=2)
    # Smoothed corner has at least one point that's NOT exactly at
    # (1, 0) — cutting moved it.
    assert all(pt != (1.0, 0.0) for pt in smoothed[1:-1])


def test_smooth_rejects_negative_iterations():
    with pytest.raises(ValueError, match=">= 0"):
        smooth_polyline([(0.0, 0.0), (1.0, 1.0)], iterations=-1)


def test_smooth_rejects_excessive_iterations():
    with pytest.raises(ValueError, match="<="):
        smooth_polyline(
            [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)],
            iterations=CHAIKIN_MAX_ITERATIONS + 1,
        )


def test_smooth_closed_polyline_wraps():
    """Closed mode should produce the same number of cuts at the
    seam as elsewhere — i.e. no kink between last point and first."""
    triangle = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
    closed = smooth_polyline(triangle, iterations=1, closed=True)
    # Closed mode emits exactly 2 * N points (cuts every segment
    # including the wrap-around), with no anchored endpoints.
    assert len(closed) == 2 * len(triangle)


def test_smooth_default_iterations_constant():
    """Sanity — the documented default is between 0 and the cap."""
    assert 0 <= CHAIKIN_DEFAULT_ITERATIONS <= CHAIKIN_MAX_ITERATIONS


def test_smooth_polyline_reduces_max_local_turn():
    """Chaikin spreads each sharp turn across multiple smaller turns;
    the maximum single-corner angle therefore shrinks even though
    total turning is approximately conserved."""
    jaggy = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0), (3.0, 1.0), (4.0, 0.0)]
    smoothed = smooth_polyline(jaggy, iterations=3)
    assert _max_turn(smoothed) < _max_turn(jaggy)


def _max_turn(polyline: list[tuple[float, float]]) -> float:
    """Largest absolute turning angle (radians) at any vertex."""
    if len(polyline) < 3:
        return 0.0
    biggest = 0.0
    for (x0, y0), (x1, y1), (x2, y2) in zip(
        polyline[:-2], polyline[1:-1], polyline[2:], strict=False,
    ):
        a = math.atan2(y1 - y0, x1 - x0)
        b = math.atan2(y2 - y1, x2 - x1)
        delta = abs(b - a)
        if delta > math.pi:
            delta = 2 * math.pi - delta
        biggest = max(biggest, delta)
    return biggest


def _total_turn(polyline: list[tuple[float, float]]) -> float:
    """Sum of absolute turning angles (radians) along a polyline."""
    if len(polyline) < 3:
        return 0.0
    total = 0.0
    for (x0, y0), (x1, y1), (x2, y2) in zip(
        polyline[:-2], polyline[1:-1], polyline[2:], strict=False,
    ):
        a = math.atan2(y1 - y0, x1 - x0)
        b = math.atan2(y2 - y1, x2 - x1)
        delta = abs(b - a)
        if delta > math.pi:
            delta = 2 * math.pi - delta
        total += delta
    return total


# ---------------------------------------------------------------------------
# Gap closing
# ---------------------------------------------------------------------------


def test_close_gaps_rejects_non_2d_input():
    bad = np.zeros((10, 10, 4), dtype=np.bool_)
    with pytest.raises(ValueError, match="2-D"):
        close_small_gaps(bad)


def test_close_gaps_rejects_non_bool_dtype():
    bad = np.zeros((10, 10), dtype=np.uint8)
    with pytest.raises(ValueError, match="bool"):
        close_small_gaps(bad)


def test_close_gaps_rejects_out_of_range_max_gap():
    mask = np.zeros((10, 10), dtype=np.bool_)
    with pytest.raises(ValueError, match="max_gap"):
        close_small_gaps(mask, max_gap=GAP_CLOSE_MAX + 1)
    with pytest.raises(ValueError, match="max_gap"):
        close_small_gaps(mask, max_gap=0)


def test_close_gaps_does_not_mutate_input():
    src = np.zeros((10, 10), dtype=np.bool_)
    src[5, 4] = True
    src[5, 6] = True
    snapshot = src.copy()
    close_small_gaps(src, max_gap=2)
    np.testing.assert_array_equal(src, snapshot)


def test_close_gaps_fills_one_pixel_break():
    """Two collinear ink dots one pixel apart — closing must connect
    them so a flood fill on either side can no longer leak through."""
    mask = np.zeros((10, 10), dtype=np.bool_)
    mask[5, 4] = True
    mask[5, 6] = True
    closed = close_small_gaps(mask, max_gap=1)
    assert closed[5, 5]


def test_close_gaps_leaves_large_gap_untouched():
    """A 5-pixel break must not be filled when ``max_gap`` is 1."""
    mask = np.zeros((20, 20), dtype=np.bool_)
    mask[10, 5] = True
    mask[10, 11] = True
    closed = close_small_gaps(mask, max_gap=1)
    assert not closed[10, 8]


def test_close_gaps_preserves_existing_ink():
    """Existing ink pixels never disappear after a close."""
    mask = np.zeros((10, 10), dtype=np.bool_)
    mask[3:7, 5] = True
    closed = close_small_gaps(mask, max_gap=1)
    assert closed[3:7, 5].all()


def test_close_gaps_returns_bool_mask():
    mask = np.zeros((6, 6), dtype=np.bool_)
    mask[3, 2] = True
    out = close_small_gaps(mask)
    assert out.dtype == np.bool_
