"""Tests for the shape primitives."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.shape_tool import (
    render_ellipse,
    render_rectangle,
    render_regular_polygon,
    render_star,
)


@pytest.fixture
def white_canvas():
    return np.full((40, 40, 4), 255, dtype=np.uint8)


def _painted(canvas: np.ndarray) -> np.ndarray:
    return (canvas[..., :3] != 255).any(axis=-1)


# ---------------------------------------------------------------------------
# render_rectangle
# ---------------------------------------------------------------------------


def test_rectangle_fill_paints_solid_block(white_canvas):
    render_rectangle(white_canvas, (5, 5, 10, 10), fill=(200, 0, 0, 255))
    assert tuple(white_canvas[10, 10]) == (200, 0, 0, 255)
    # Outside the rect stays white.
    assert tuple(white_canvas[20, 20]) == (255, 255, 255, 255)


def test_rectangle_stroke_paints_only_edges(white_canvas):
    render_rectangle(
        white_canvas, (5, 5, 10, 10),
        stroke=(0, 0, 0, 255), stroke_width=1,
    )
    # Edges should be black; interior should remain white.
    assert tuple(white_canvas[5, 10]) == (0, 0, 0, 255)
    assert tuple(white_canvas[10, 10]) == (255, 255, 255, 255)


def test_rectangle_fill_then_stroke_overlays(white_canvas):
    render_rectangle(
        white_canvas, (5, 5, 10, 10),
        fill=(255, 200, 0, 255), stroke=(0, 0, 0, 255), stroke_width=2,
    )
    # Edge is stroke colour, interior is fill colour.
    assert tuple(white_canvas[5, 10]) == (0, 0, 0, 255)
    assert tuple(white_canvas[10, 10]) == (255, 200, 0, 255)


def test_rectangle_no_fill_no_stroke_is_noop(white_canvas):
    snapshot = white_canvas.copy()
    render_rectangle(white_canvas, (5, 5, 10, 10))
    np.testing.assert_array_equal(white_canvas, snapshot)


def test_rectangle_off_canvas_returns_empty_damage(white_canvas):
    rect = render_rectangle(
        white_canvas, (-100, -100, 5, 5), fill=(200, 0, 0, 255),
    )
    assert rect.is_empty


def test_rectangle_clips_to_canvas_bounds(white_canvas):
    """A rect that pokes off the right edge still paints what fits."""
    render_rectangle(
        white_canvas, (35, 5, 100, 10), fill=(200, 0, 0, 255),
    )
    # The visible part inside the canvas should be painted.
    assert tuple(white_canvas[10, 38]) == (200, 0, 0, 255)


# ---------------------------------------------------------------------------
# render_ellipse
# ---------------------------------------------------------------------------


def test_ellipse_fill_at_centre(white_canvas):
    render_ellipse(white_canvas, (5, 5, 20, 20), fill=(50, 200, 50, 255))
    centre = white_canvas[15, 15]
    assert tuple(centre) == (50, 200, 50, 255)


def test_ellipse_corners_unpainted(white_canvas):
    render_ellipse(white_canvas, (5, 5, 20, 20), fill=(0, 200, 0, 255))
    # The corners of the bounding box are outside the ellipse.
    assert tuple(white_canvas[5, 5]) == (255, 255, 255, 255)
    assert tuple(white_canvas[5, 24]) == (255, 255, 255, 255)


def test_ellipse_stroke_paints_only_perimeter(white_canvas):
    render_ellipse(
        white_canvas, (5, 5, 20, 20),
        stroke=(0, 0, 0, 255), stroke_width=2,
    )
    # Centre stays white.
    assert tuple(white_canvas[15, 15]) == (255, 255, 255, 255)
    # Perimeter region has paint somewhere.
    assert _painted(white_canvas).any()


def test_ellipse_zero_size_rect_is_noop(white_canvas):
    snapshot = white_canvas.copy()
    rect = render_ellipse(white_canvas, (5, 5, 0, 0), fill=(0, 200, 0, 255))
    assert rect.is_empty
    np.testing.assert_array_equal(white_canvas, snapshot)


# ---------------------------------------------------------------------------
# render_regular_polygon
# ---------------------------------------------------------------------------


def test_polygon_triangle_paints_three_corners(white_canvas):
    render_regular_polygon(
        white_canvas, center=(20.0, 20.0), radius=10.0, n_sides=3,
        fill=(200, 0, 0, 255), rotation_deg=-90.0,
    )
    # Top vertex (20, 10) area should be painted.
    assert tuple(white_canvas[10, 20]) == (200, 0, 0, 255)
    # Centre painted.
    assert tuple(white_canvas[20, 20]) == (200, 0, 0, 255)


def test_polygon_hexagon_centre_painted(white_canvas):
    render_regular_polygon(
        white_canvas, center=(20.0, 20.0), radius=10.0, n_sides=6,
        fill=(0, 0, 200, 255),
    )
    assert tuple(white_canvas[20, 20]) == (0, 0, 200, 255)


def test_polygon_rejects_under_three_sides(white_canvas):
    with pytest.raises(ValueError, match="n_sides"):
        render_regular_polygon(
            white_canvas, center=(20.0, 20.0), radius=10.0, n_sides=2,
            fill=(0, 0, 0, 255),
        )


def test_polygon_rejects_zero_radius(white_canvas):
    with pytest.raises(ValueError, match="radius"):
        render_regular_polygon(
            white_canvas, center=(20.0, 20.0), radius=0.0, n_sides=5,
            fill=(0, 0, 0, 255),
        )


def test_polygon_stroke_only_leaves_centre_white(white_canvas):
    render_regular_polygon(
        white_canvas, center=(20.0, 20.0), radius=12.0, n_sides=6,
        stroke=(0, 0, 0, 255), stroke_width=1,
    )
    assert tuple(white_canvas[20, 20]) == (255, 255, 255, 255)


# ---------------------------------------------------------------------------
# render_star
# ---------------------------------------------------------------------------


def test_star_5_point_centre_painted(white_canvas):
    render_star(
        white_canvas, center=(20.0, 20.0), outer_radius=12.0, n_points=5,
        fill=(255, 220, 0, 255),
    )
    assert tuple(white_canvas[20, 20]) == (255, 220, 0, 255)


def test_star_default_inner_is_half_of_outer(white_canvas):
    """Default inner radius = 0.5 * outer — at top tip the star is
    painted, at the valley between tips the canvas isn't (because the
    valley is closer to the centre and inside the inner radius)."""
    render_star(
        white_canvas, center=(20.0, 20.0), outer_radius=10.0, n_points=5,
        fill=(0, 100, 200, 255), rotation_deg=-90.0,
    )
    # Top tip is at y ≈ 10.
    assert tuple(white_canvas[10, 20]) == (0, 100, 200, 255)


def test_star_explicit_inner_radius_used(white_canvas):
    render_star(
        white_canvas, center=(20.0, 20.0), outer_radius=10.0, n_points=5,
        inner_radius=4.0, fill=(0, 100, 200, 255),
    )
    assert tuple(white_canvas[20, 20]) == (0, 100, 200, 255)


def test_star_rejects_inner_above_outer(white_canvas):
    with pytest.raises(ValueError, match="inner"):
        render_star(
            white_canvas, center=(20.0, 20.0), outer_radius=10.0, n_points=5,
            inner_radius=20.0, fill=(0, 0, 0, 255),
        )


def test_star_rejects_zero_inner(white_canvas):
    with pytest.raises(ValueError, match="inner"):
        render_star(
            white_canvas, center=(20.0, 20.0), outer_radius=10.0, n_points=5,
            inner_radius=0.0, fill=(0, 0, 0, 255),
        )


def test_star_rejects_under_three_points(white_canvas):
    with pytest.raises(ValueError, match="n_points"):
        render_star(
            white_canvas, center=(20.0, 20.0), outer_radius=10.0, n_points=2,
            fill=(0, 0, 0, 255),
        )


# ---------------------------------------------------------------------------
# Canvas validation
# ---------------------------------------------------------------------------


def test_rectangle_rejects_non_rgba_canvas():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        render_rectangle(rgb, (0, 0, 5, 5), fill=(0, 0, 0, 255))


def test_ellipse_rejects_wrong_dtype():
    canvas = np.zeros((10, 10, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="HxWx4"):
        render_ellipse(canvas, (0, 0, 5, 5), fill=(0, 0, 0, 255))
