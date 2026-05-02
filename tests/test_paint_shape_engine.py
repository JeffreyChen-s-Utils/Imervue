"""Tests for the rect / ellipse / line / polygon rasterisers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.shape_engine import (
    SHAPE_MODES,
    rasterise_ellipse,
    rasterise_line,
    rasterise_polygon,
    rasterise_rect,
)

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


@pytest.fixture
def canvas():
    return np.zeros((32, 32, 4), dtype=np.uint8)


# ---------------------------------------------------------------------------
# rasterise_rect
# ---------------------------------------------------------------------------


def test_rect_fills_inside_box(canvas):
    rasterise_rect(canvas, 4, 4, 10, 10, RED, mode="fill")
    assert tuple(canvas[8, 8]) == RED
    # Outside is still transparent.
    assert tuple(canvas[0, 0]) == (0, 0, 0, 0)


def test_rect_with_negative_dims_is_normalised(canvas):
    """Drag from bottom-right back to top-left should still produce
    the same rectangle as a forward drag."""
    rasterise_rect(canvas, 14, 14, -10, -10, RED, mode="fill")
    assert tuple(canvas[8, 8]) == RED


def test_rect_clipped_to_canvas(canvas):
    """A rect that extends past the canvas must not write out of
    bounds; the helper just truncates."""
    handled = rasterise_rect(canvas, 28, 28, 100, 100, RED, mode="fill")
    assert handled is True
    # Bottom-right corner of canvas is filled.
    assert tuple(canvas[31, 31]) == RED


def test_rect_too_small_is_noop(canvas):
    handled = rasterise_rect(canvas, 4, 4, 0, 0, RED, mode="fill")
    assert handled is False
    assert canvas.sum() == 0


def test_rect_stroke_paints_only_border(canvas):
    rasterise_rect(canvas, 4, 4, 12, 12, RED, mode="stroke", stroke_width=2)
    # Top row of the rect should be opaque red.
    assert tuple(canvas[4, 8]) == RED
    # Centre should still be transparent.
    assert tuple(canvas[10, 10]) == (0, 0, 0, 0)


def test_rect_both_paints_fill_and_border(canvas):
    rasterise_rect(canvas, 4, 4, 12, 12, RED, mode="both", stroke_width=2)
    # Both edge AND centre opaque.
    assert tuple(canvas[10, 10]) == RED
    assert tuple(canvas[4, 8]) == RED


def test_rect_rejects_unknown_mode(canvas):
    with pytest.raises(ValueError):
        rasterise_rect(canvas, 4, 4, 10, 10, RED, mode="diagonal")


def test_rect_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        rasterise_rect(bad, 0, 0, 4, 4, RED)


# ---------------------------------------------------------------------------
# rasterise_ellipse
# ---------------------------------------------------------------------------


def test_ellipse_fills_centre(canvas):
    rasterise_ellipse(canvas, 16, 16, 8, 8, RED, mode="fill")
    assert tuple(canvas[16, 16]) == RED
    # Far corner outside the disc.
    assert tuple(canvas[0, 0]) == (0, 0, 0, 0)


def test_ellipse_with_zero_radius_clamped(canvas):
    """A zero-radius ellipse becomes a single-pixel dab — still
    visible rather than silently disappearing."""
    handled = rasterise_ellipse(canvas, 16, 16, 0, 0, RED)
    assert handled is True


def test_ellipse_stroke_only_paints_rim(canvas):
    rasterise_ellipse(canvas, 16, 16, 10, 10, RED,
                      mode="stroke", stroke_width=2)
    # Ring at the edge but not the centre.
    assert tuple(canvas[16, 16]) == (0, 0, 0, 0)
    # Pixel near the rim is painted.
    rim = canvas[16, 6]
    assert tuple(rim) == RED


def test_ellipse_with_uneven_axes_is_oval(canvas):
    """rx > ry produces a horizontal oval — pixels far horizontally
    are still inside, pixels far vertically are not."""
    rasterise_ellipse(canvas, 16, 16, 12, 4, RED, mode="fill")
    # 12 to the right is just on the rim → painted.
    assert tuple(canvas[16, 28]) == RED
    # 8 below (>4 ry) is outside.
    assert tuple(canvas[24, 16]) == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# rasterise_line
# ---------------------------------------------------------------------------


def test_line_paints_endpoints(canvas):
    rasterise_line(canvas, 4, 4, 28, 28, RED, width=2)
    assert tuple(canvas[4, 4]) == RED
    assert tuple(canvas[28, 28]) == RED


def test_line_zero_length_still_paints_dot(canvas):
    """A click without drag should leave a visible dab — not a no-op."""
    handled = rasterise_line(canvas, 16, 16, 16, 16, RED, width=3)
    assert handled is True
    assert tuple(canvas[16, 16]) == RED


def test_line_rejects_zero_width(canvas):
    with pytest.raises(ValueError):
        rasterise_line(canvas, 0, 0, 4, 4, RED, width=0)


def test_line_paints_horizontal(canvas):
    rasterise_line(canvas, 4, 16, 28, 16, RED, width=1)
    # Several pixels along the line are painted.
    assert tuple(canvas[16, 10]) == RED
    assert tuple(canvas[16, 20]) == RED


# ---------------------------------------------------------------------------
# rasterise_polygon
# ---------------------------------------------------------------------------


def test_polygon_with_three_points_fills_triangle(canvas):
    points = [(4, 4), (28, 4), (16, 28)]
    rasterise_polygon(canvas, points, RED, mode="fill")
    # Centroid of the triangle is inside.
    cy = (4 + 4 + 28) // 3
    cx = (4 + 28 + 16) // 3
    assert tuple(canvas[cy, cx]) == RED


def test_polygon_one_point_paints_dot(canvas):
    rasterise_polygon(canvas, [(16, 16)], RED, mode="fill")
    assert tuple(canvas[16, 16]) == RED


def test_polygon_two_points_paints_line(canvas):
    rasterise_polygon(canvas, [(4, 4), (28, 28)], RED, mode="fill")
    assert tuple(canvas[4, 4]) == RED
    assert tuple(canvas[28, 28]) == RED


def test_polygon_empty_points_is_noop(canvas):
    assert rasterise_polygon(canvas, [], RED) is False
    assert canvas.sum() == 0


def test_polygon_stroke_paints_perimeter_only(canvas):
    """A polygon stroked-only should have its centre transparent."""
    points = [(4, 4), (28, 4), (28, 28), (4, 28)]   # square
    rasterise_polygon(canvas, points, RED,
                      mode="stroke", stroke_width=2)
    # Edge painted.
    assert tuple(canvas[4, 16]) == RED
    # Centre untouched.
    assert tuple(canvas[16, 16]) == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# Mode catalogue
# ---------------------------------------------------------------------------


def test_shape_modes_lists_three_values():
    assert set(SHAPE_MODES) == {"fill", "stroke", "both"}
