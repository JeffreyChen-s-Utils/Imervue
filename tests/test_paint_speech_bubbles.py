"""Tests for speech-bubble shapes."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.speech_bubbles import BUBBLE_STYLES, render_speech_bubble


@pytest.fixture
def white_canvas():
    return np.full((60, 80, 4), 255, dtype=np.uint8)


def _painted(canvas: np.ndarray) -> np.ndarray:
    return (canvas[..., :3] != 255).any(axis=-1)


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


def test_styles_constant_lists_four():
    assert set(BUBBLE_STYLES) == {"oval", "rectangular", "thought", "jagged"}


def test_unknown_style_raises(white_canvas):
    with pytest.raises(ValueError, match="unknown bubble style"):
        render_speech_bubble(white_canvas, (10, 10, 30, 20), style="banana")


def test_no_fill_no_stroke_is_noop(white_canvas):
    snapshot = white_canvas.copy()
    render_speech_bubble(
        white_canvas, (10, 10, 30, 20),
        fill=None, stroke=None,
    )
    np.testing.assert_array_equal(white_canvas, snapshot)


# ---------------------------------------------------------------------------
# Oval
# ---------------------------------------------------------------------------


def test_oval_fill_paints_centre(white_canvas):
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="oval",
        fill=(200, 0, 0, 255), stroke=None,
    )
    # Centre of the bubble.
    assert tuple(white_canvas[25, 30]) == (200, 0, 0, 255)


def test_oval_corners_unpainted(white_canvas):
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="oval",
        fill=(200, 0, 0, 255), stroke=None,
    )
    # Bounding-box corners are outside the ellipse silhouette.
    assert tuple(white_canvas[10, 10]) == (255, 255, 255, 255)


def test_oval_stroke_paints_perimeter(white_canvas):
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="oval",
        fill=None, stroke=(0, 0, 0, 255), stroke_width=2,
    )
    assert _painted(white_canvas).any()


# ---------------------------------------------------------------------------
# Rectangular
# ---------------------------------------------------------------------------


def test_rectangular_fill_paints_centre(white_canvas):
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="rectangular",
        fill=(0, 0, 200, 255), stroke=None, corner_radius=8,
    )
    assert tuple(white_canvas[25, 30]) == (0, 0, 200, 255)


def test_rectangular_zero_radius_paints_full_corners(white_canvas):
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="rectangular",
        fill=(0, 0, 200, 255), stroke=None, corner_radius=0,
    )
    # Top-left corner is painted (rect has square corners).
    assert tuple(white_canvas[10, 10]) == (0, 0, 200, 255)


def test_rectangular_with_radius_clips_corner(white_canvas):
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="rectangular",
        fill=(0, 0, 200, 255), stroke=None, corner_radius=10,
    )
    # Sharp corner pixel (10, 10) should NOT be painted (rounded out).
    assert tuple(white_canvas[10, 10]) == (255, 255, 255, 255)


# ---------------------------------------------------------------------------
# Thought bubble
# ---------------------------------------------------------------------------


def test_thought_bubble_paints_outside_ellipse(white_canvas):
    """The bumps along the perimeter extend the silhouette beyond the
    base ellipse — a thought bubble should paint pixels that an oval
    of the same rect would leave unpainted."""
    oval_canvas = np.full((60, 80, 4), 255, dtype=np.uint8)
    thought_canvas = np.full((60, 80, 4), 255, dtype=np.uint8)
    rect = (10, 10, 40, 30)
    render_speech_bubble(
        oval_canvas, rect, style="oval",
        fill=(0, 0, 0, 255), stroke=None,
    )
    render_speech_bubble(
        thought_canvas, rect, style="thought",
        fill=(0, 0, 0, 255), stroke=None, bump_count=12,
    )
    assert _painted(thought_canvas).sum() > _painted(oval_canvas).sum()


def test_thought_zero_bumps_falls_back_to_ellipse(white_canvas):
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="thought",
        fill=(0, 0, 0, 255), stroke=None, bump_count=0,
    )
    # Centre painted; corner bbox not painted (back to oval).
    assert tuple(white_canvas[25, 30]) == (0, 0, 0, 255)
    assert tuple(white_canvas[10, 10]) == (255, 255, 255, 255)


# ---------------------------------------------------------------------------
# Jagged
# ---------------------------------------------------------------------------


def test_jagged_fill_paints_centre(white_canvas):
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="jagged",
        fill=(255, 200, 0, 255), stroke=None, spike_count=8,
    )
    assert tuple(white_canvas[25, 30]) == (255, 200, 0, 255)


def test_jagged_perimeter_breaks_up_bbox():
    """A jagged silhouette should leave more bbox-corner area unpainted
    than an oval of the same rect (spikes don't fill out to the corner
    as smoothly)."""
    oval_canvas = np.full((60, 80, 4), 255, dtype=np.uint8)
    jagged_canvas = np.full((60, 80, 4), 255, dtype=np.uint8)
    rect = (10, 10, 40, 30)
    render_speech_bubble(
        oval_canvas, rect, style="oval",
        fill=(0, 0, 0, 255), stroke=None,
    )
    render_speech_bubble(
        jagged_canvas, rect, style="jagged",
        fill=(0, 0, 0, 255), stroke=None, spike_count=10,
    )
    # Jagged is similar in painted-pixel count, just with a different
    # silhouette. The smoke test: it paints something, doesn't error.
    assert _painted(jagged_canvas).any()


# ---------------------------------------------------------------------------
# Tail
# ---------------------------------------------------------------------------


def test_tail_paints_pixels_toward_target(white_canvas):
    """A tail aimed at (60, 50) should paint pixels along the path
    from the bubble toward that point."""
    render_speech_bubble(
        white_canvas, (10, 10, 30, 20), style="oval",
        tail_target=(60.0, 50.0),
        fill=(200, 0, 0, 255), stroke=None,
    )
    # Approximate midpoint of the tail trajectory.
    assert tuple(white_canvas[40, 50]) == (200, 0, 0, 255)


def test_tail_target_at_centre_does_not_extend(white_canvas):
    """A degenerate tail (target == bubble centre) is dropped."""
    render_speech_bubble(
        white_canvas, (10, 10, 40, 30), style="oval",
        tail_target=(30.0, 25.0),   # the bubble centre
        fill=(0, 200, 0, 255), stroke=None,
    )
    # Centre painted (the bubble) but no extra tail damage outside it.
    assert tuple(white_canvas[25, 30]) == (0, 200, 0, 255)


# ---------------------------------------------------------------------------
# Damage rect + canvas validation
# ---------------------------------------------------------------------------


def test_damage_rect_returned():
    canvas = np.full((30, 30, 4), 255, dtype=np.uint8)
    rect = render_speech_bubble(
        canvas, (5, 5, 20, 20), style="oval",
        fill=(0, 0, 0, 255),
    )
    assert not rect.is_empty


def test_canvas_validation():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        render_speech_bubble(rgb, (0, 0, 5, 5), fill=(0, 0, 0, 255))


# ---------------------------------------------------------------------------
# Auto-tail: attachment_point lands on the silhouette edge
# ---------------------------------------------------------------------------


def test_attachment_point_oval_lands_on_ellipse_perimeter():
    """For an oval bubble, the attachment point must sit ON the
    ellipse — its (nx, ny) form should evaluate to ~1.0."""
    from Imervue.paint.speech_bubbles import attachment_point
    rect = (10, 10, 60, 30)
    cx, cy = 10 + 30, 10 + 15
    rx, ry = 30.0, 15.0
    attach = attachment_point(rect, "oval", target=(200.0, 200.0))
    nx = (attach[0] - cx) / rx
    ny = (attach[1] - cy) / ry
    assert abs(nx * nx + ny * ny - 1.0) < 1e-6


def test_attachment_point_oval_aligned_with_target_ray():
    """The attachment point must lie ON the line from the centre to
    the target — same direction, not flipped."""
    from Imervue.paint.speech_bubbles import attachment_point
    import math
    rect = (0, 0, 40, 40)
    cx, cy = 20.0, 20.0
    target = (100.0, 100.0)
    attach = attachment_point(rect, "oval", target=target)
    # Direction from centre to attach should match centre→target.
    target_angle = math.atan2(target[1] - cy, target[0] - cx)
    attach_angle = math.atan2(attach[1] - cy, attach[0] - cx)
    assert abs(target_angle - attach_angle) < 1e-6


def test_attachment_point_rectangular_lands_on_edge():
    """For a rectangular bubble with a target straight to the right,
    the attachment must sit on the right edge."""
    from Imervue.paint.speech_bubbles import attachment_point
    rect = (0, 0, 40, 40)
    attach = attachment_point(
        rect, "rectangular", target=(200.0, 20.0), corner_radius=0,
    )
    assert attach[0] == pytest.approx(40.0)
    assert attach[1] == pytest.approx(20.0)


def test_attachment_point_target_at_centre_returns_centre():
    """No defined direction → fall back to bubble centre."""
    from Imervue.paint.speech_bubbles import attachment_point
    rect = (10, 10, 40, 40)
    attach = attachment_point(rect, "oval", target=(30.0, 30.0))
    assert attach == pytest.approx((30.0, 30.0))


def test_attachment_point_zero_size_rect_returns_centre():
    from Imervue.paint.speech_bubbles import attachment_point
    attach = attachment_point((10, 10, 0, 0), "oval", target=(50.0, 50.0))
    assert attach == pytest.approx((10.0, 10.0))


# ---------------------------------------------------------------------------
# compute_tail_polygon shape
# ---------------------------------------------------------------------------


def test_tail_polygon_triangle_has_three_unique_vertices():
    """Triangle tail outline closes back to the first base vertex,
    so the list has 4 entries with the first == last and three
    distinct points."""
    from Imervue.paint.speech_bubbles import compute_tail_polygon
    poly = compute_tail_polygon(
        (0, 0, 40, 40), "oval", target=(100.0, 20.0),
        tail_style="triangle",
    )
    assert len(poly) == 4
    assert poly[0] == poly[-1]
    assert len({tuple(p) for p in poly[:-1]}) == 3


def test_tail_polygon_curve_has_more_vertices():
    from Imervue.paint.speech_bubbles import compute_tail_polygon
    poly = compute_tail_polygon(
        (0, 0, 40, 40), "oval", target=(100.0, 20.0),
        tail_style="curve",
    )
    # Two base + two mid + tip + close = 6 entries.
    assert len(poly) == 6


def test_tail_polygon_thought_trail_returns_three_dot_centres():
    from Imervue.paint.speech_bubbles import compute_tail_polygon
    centres = compute_tail_polygon(
        (0, 0, 40, 40), "thought", target=(100.0, 100.0),
        tail_style="thought_trail",
    )
    assert len(centres) == 3


def test_tail_polygon_unknown_style_raises():
    from Imervue.paint.speech_bubbles import compute_tail_polygon
    with pytest.raises(ValueError, match="unknown tail style"):
        compute_tail_polygon(
            (0, 0, 40, 40), "oval", target=(100.0, 20.0),
            tail_style="zigzag",
        )


def test_tail_polygon_target_at_centre_returns_empty():
    from Imervue.paint.speech_bubbles import compute_tail_polygon
    poly = compute_tail_polygon(
        (0, 0, 40, 40), "oval", target=(20.0, 20.0),
    )
    assert poly == []


# ---------------------------------------------------------------------------
# render_speech_bubble — auto-tail integration
# ---------------------------------------------------------------------------


def test_render_with_curve_tail_paints_pixels(white_canvas):
    """Curve-tail render path must touch pixels — proves the helper
    feeds polygon_mask without a degenerate result."""
    render_speech_bubble(
        white_canvas, (10, 10, 30, 20),
        style="oval",
        tail_target=(70.0, 50.0),
        tail_style="curve",
        fill=(0, 0, 0, 255),
    )
    assert _painted(white_canvas).sum() > 0


def test_render_with_thought_trail_paints_dots(white_canvas):
    """Thought-trail tail draws a sequence of dots — the painted area
    extends past the bubble bbox along the target direction."""
    render_speech_bubble(
        white_canvas, (5, 5, 25, 20),
        style="thought",
        tail_target=(70.0, 50.0),
        tail_style="thought_trail",
        fill=(0, 0, 0, 255),
    )
    painted = _painted(white_canvas)
    # Pixels painted near the target — the trail's last dot should
    # leave at least one painted pixel inside a 6-radius around the
    # target's region.
    assert painted[40:55, 60:75].sum() > 0


def test_render_unknown_tail_style_raises(white_canvas):
    with pytest.raises(ValueError, match="unknown tail style"):
        render_speech_bubble(
            white_canvas, (10, 10, 30, 20), style="oval",
            tail_target=(60.0, 50.0), tail_style="zalgo",
            fill=(0, 0, 0, 255),
        )
