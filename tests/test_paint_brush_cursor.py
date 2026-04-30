"""Tests for the brush cursor ring renderer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.brush_cursor import (
    cursor_bbox,
    render_cursor_ring,
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_render_cursor_ring_rejects_zero_canvas():
    with pytest.raises(ValueError, match="canvas_size"):
        render_cursor_ring((0, 0), 0, 0, 5)


def test_render_cursor_ring_rejects_negative_radius():
    with pytest.raises(ValueError, match="radius"):
        render_cursor_ring((20, 20), 10, 10, -1)


def test_render_cursor_ring_rejects_oversized_radius():
    with pytest.raises(ValueError, match="radius"):
        render_cursor_ring((20, 20), 10, 10, 99999)


def test_render_cursor_ring_rejects_zero_thickness():
    with pytest.raises(ValueError, match="thickness"):
        render_cursor_ring((20, 20), 10, 10, 5, thickness=0)


def test_render_cursor_ring_rejects_oversized_thickness():
    with pytest.raises(ValueError, match="thickness"):
        render_cursor_ring((20, 20), 10, 10, 5, thickness=100)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def test_render_cursor_ring_returns_canvas_sized_buffer():
    out = render_cursor_ring((30, 40), 20, 15, 5)
    assert out.shape == (30, 40, 4)
    assert out.dtype == np.uint8


def test_render_cursor_ring_centre_not_painted():
    """The ring is hollow — the centre pixel stays transparent."""
    out = render_cursor_ring((40, 40), 20, 20, 8)
    assert out[20, 20, 3] == 0


def test_render_cursor_ring_paints_at_radius():
    """A pixel at exactly ``radius`` from the centre lies on the ring."""
    out = render_cursor_ring((40, 40), 20, 20, 8)
    # (28, 20) is 8 pixels right of centre.
    assert out[20, 28, 3] > 0


def test_render_cursor_ring_outside_radius_unpainted():
    out = render_cursor_ring((40, 40), 20, 20, 5)
    # Far edge of canvas, well outside the ring.
    assert out[0, 0, 3] == 0


def test_render_cursor_ring_thicker_paints_more():
    thin = render_cursor_ring((40, 40), 20, 20, 8, thickness=1)
    thick = render_cursor_ring((40, 40), 20, 20, 8, thickness=4)
    assert (thick[..., 3] > 0).sum() > (thin[..., 3] > 0).sum()


def test_render_cursor_ring_inner_radius_paints_second_circle():
    no_inner = render_cursor_ring((40, 40), 20, 20, 8)
    with_inner = render_cursor_ring(
        (40, 40), 20, 20, 8, inner_radius=4,
    )
    assert (with_inner[..., 3] > 0).sum() > (no_inner[..., 3] > 0).sum()


def test_render_cursor_ring_inner_geq_outer_raises():
    with pytest.raises(ValueError, match="inner_radius"):
        render_cursor_ring((40, 40), 20, 20, 4, inner_radius=8)


def test_render_cursor_ring_zero_radius_no_inner_returns_empty():
    out = render_cursor_ring((20, 20), 10, 10, 0)
    assert out[..., 3].sum() == 0


def test_render_cursor_ring_color_applied():
    out = render_cursor_ring(
        (40, 40), 20, 20, 8, color=(255, 100, 50, 200),
    )
    ys, xs = np.where(out[..., 3] > 0)
    sample = out[ys[0], xs[0]]
    assert tuple(sample) == (255, 100, 50, 200)


def test_render_cursor_ring_off_canvas_centre_clipped():
    """Drawing a ring whose centre is outside the canvas still paints
    the visible portion without raising."""
    out = render_cursor_ring((20, 20), -5, -5, 10)
    # Some pixels in the top-left quadrant might be on-ring.
    assert out.shape == (20, 20, 4)


# ---------------------------------------------------------------------------
# cursor_bbox
# ---------------------------------------------------------------------------


def test_cursor_bbox_contains_ring():
    bbox = cursor_bbox(20, 20, 8)
    x, y, w, h = bbox
    # All of (12, 28) on the x axis must lie within the box.
    assert x <= 12
    assert x + w >= 28


def test_cursor_bbox_grows_with_thickness():
    thin = cursor_bbox(20, 20, 8, thickness=1)
    thick = cursor_bbox(20, 20, 8, thickness=10)
    assert thick[2] > thin[2]
    assert thick[3] > thin[3]


def test_cursor_bbox_shrinks_with_smaller_radius():
    big = cursor_bbox(20, 20, 16)
    small = cursor_bbox(20, 20, 4)
    assert big[2] > small[2]
