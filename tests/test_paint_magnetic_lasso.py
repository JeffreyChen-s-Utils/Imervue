"""Tests for the edge-snapping magnetic lasso helper."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.magnetic_lasso import (
    MAX_SEARCH_RADIUS,
    edge_magnitude,
    snap_path_to_edges,
    snap_to_edge,
)


def _vertical_edge_image(h=20, w=20, edge_x=10):
    """White on the left, black on the right with a vertical edge."""
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[:, :edge_x, :3] = 255   # white left
    # right side stays black
    return img


def _uniform_image(h=10, w=10, color=(128, 128, 128)):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., :3] = color
    img[..., 3] = 255
    return img


# ---------------------------------------------------------------------------
# edge_magnitude
# ---------------------------------------------------------------------------


def test_edge_magnitude_high_at_edge():
    img = _vertical_edge_image(h=20, w=20, edge_x=10)
    em = edge_magnitude(img)
    # Magnitude should peak near column 10.
    peak_col = int(np.argmax(em.sum(axis=0)))
    assert abs(peak_col - 10) <= 1


def test_edge_magnitude_uniform_returns_zero():
    img = _uniform_image()
    em = edge_magnitude(img)
    assert em.max() == pytest.approx(0.0)


def test_edge_magnitude_rejects_non_rgba():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        edge_magnitude(rgb)


# ---------------------------------------------------------------------------
# snap_to_edge
# ---------------------------------------------------------------------------


def test_snap_to_edge_pulls_anchor_to_nearest_edge():
    img = _vertical_edge_image(h=20, w=20, edge_x=10)
    # Anchor 3 px to the right of the edge.
    snapped = snap_to_edge(img, (13, 10), search_radius=5)
    # Should land at or very near x=10.
    assert abs(snapped[0] - 10) <= 1


def test_snap_to_edge_uniform_image_returns_anchor():
    img = _uniform_image(h=20, w=20)
    snapped = snap_to_edge(img, (5, 5), search_radius=4)
    assert snapped == (5, 5)


def test_snap_to_edge_zero_radius_returns_anchor():
    img = _vertical_edge_image()
    snapped = snap_to_edge(img, (5, 5), search_radius=0)
    assert snapped == (5, 5)


def test_snap_to_edge_off_canvas_anchor_returns_anchor():
    img = _vertical_edge_image()
    snapped = snap_to_edge(img, (-5, 100), search_radius=4)
    assert snapped == (-5, 100)


def test_snap_to_edge_out_of_range_radius_raises():
    img = _vertical_edge_image()
    with pytest.raises(ValueError, match="search_radius"):
        snap_to_edge(img, (5, 5), search_radius=MAX_SEARCH_RADIUS + 1)
    with pytest.raises(ValueError, match="search_radius"):
        snap_to_edge(img, (5, 5), search_radius=-1)


def test_snap_to_edge_pre_computed_edge_map_reused():
    img = _vertical_edge_image()
    em = edge_magnitude(img)
    snapped_a = snap_to_edge(img, (13, 10), search_radius=5, edge_map=em)
    snapped_b = snap_to_edge(img, (13, 10), search_radius=5)
    assert snapped_a == snapped_b


def test_snap_to_edge_rejects_mismatched_edge_map():
    img = _vertical_edge_image(h=20, w=20)
    bad_em = np.zeros((10, 10), dtype=np.float32)
    with pytest.raises(ValueError, match="does not match"):
        snap_to_edge(img, (5, 5), search_radius=5, edge_map=bad_em)


def test_snap_to_edge_rejects_non_rgba():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        snap_to_edge(rgb, (5, 5))


def test_snap_to_edge_far_from_edge_returns_uniform_pixel():
    """Anchor far from any edge with a small radius — every pixel in
    the search window has zero edge magnitude, so the anchor is
    returned unchanged."""
    img = _vertical_edge_image(h=40, w=40, edge_x=10)
    snapped = snap_to_edge(img, (35, 35), search_radius=2)
    assert snapped == (35, 35)


# ---------------------------------------------------------------------------
# snap_path_to_edges
# ---------------------------------------------------------------------------


def test_snap_path_to_edges_returns_one_per_input():
    img = _vertical_edge_image()
    anchors = [(13, 5), (13, 10), (13, 15)]
    out = snap_path_to_edges(img, anchors, search_radius=5)
    assert len(out) == 3


def test_snap_path_to_edges_pulls_each_anchor_toward_edge():
    img = _vertical_edge_image()
    anchors = [(13, 5), (13, 10), (13, 15)]
    out = snap_path_to_edges(img, anchors, search_radius=5)
    for snapped in out:
        assert abs(snapped[0] - 10) <= 1


def test_snap_path_to_edges_empty_anchors_returns_empty():
    img = _vertical_edge_image()
    assert snap_path_to_edges(img, []) == []
