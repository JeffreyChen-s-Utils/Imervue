"""Tests for the mesh-warp transform engine."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.mesh_warp import (
    DEFAULT_GRID_DIM,
    MAX_GRID_DIM,
    MIN_GRID_DIM,
    MeshGrid,
    warp_image,
)


def _checker(h: int = 32, w: int = 32, cell: int = 8) -> np.ndarray:
    """Asymmetric pattern so warps produce visible differences."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 3] = 255
    yy, xx = np.indices((h, w))
    is_dark = ((xx // cell) + (yy // cell)) % 2 == 0
    arr[is_dark, 0] = 255
    return arr


# ---------------------------------------------------------------------------
# MeshGrid construction + invariants
# ---------------------------------------------------------------------------


def test_identity_grid_default_dimensions():
    grid = MeshGrid.identity(64, 32)
    assert grid.rows == DEFAULT_GRID_DIM
    assert grid.cols == DEFAULT_GRID_DIM
    assert grid.destination.shape == (DEFAULT_GRID_DIM, DEFAULT_GRID_DIM, 2)
    assert grid.destination.dtype == np.float32


def test_identity_grid_corners_at_image_corners():
    grid = MeshGrid.identity(40, 20)
    assert grid.destination_node(0, 0) == (0.0, 0.0)
    assert grid.destination_node(0, grid.cols - 1) == (39.0, 0.0)
    assert grid.destination_node(grid.rows - 1, 0) == (0.0, 19.0)


def test_identity_grid_is_identity():
    grid = MeshGrid.identity(32, 32)
    assert grid.is_identity()


def test_grid_rejects_too_few_rows():
    bad_dest = np.zeros((1, 4, 2), dtype=np.float32)
    with pytest.raises(ValueError):
        MeshGrid(width=32, height=32, rows=1, cols=4, destination=bad_dest)


def test_grid_rejects_too_many_rows():
    big = MAX_GRID_DIM + 2
    bad_dest = np.zeros((big, 4, 2), dtype=np.float32)
    with pytest.raises(ValueError):
        MeshGrid(width=32, height=32, rows=big, cols=4, destination=bad_dest)


def test_grid_rejects_destination_dtype_mismatch():
    bad_dest = np.zeros((4, 4, 2), dtype=np.float64)
    with pytest.raises(ValueError):
        MeshGrid(width=32, height=32, rows=4, cols=4, destination=bad_dest)


def test_grid_rejects_destination_shape_mismatch():
    bad_dest = np.zeros((3, 4, 2), dtype=np.float32)
    with pytest.raises(ValueError):
        MeshGrid(width=32, height=32, rows=4, cols=4, destination=bad_dest)


def test_grid_rejects_zero_dimensions():
    dest = np.zeros((4, 4, 2), dtype=np.float32)
    with pytest.raises(ValueError):
        MeshGrid(width=0, height=32, rows=4, cols=4, destination=dest)


# ---------------------------------------------------------------------------
# source_node / destination_node / move_destination_node
# ---------------------------------------------------------------------------


def test_source_node_corners_match_image_corners():
    grid = MeshGrid.identity(40, 20)
    assert grid.source_node(0, 0) == (0.0, 0.0)
    assert grid.source_node(0, grid.cols - 1)[0] == pytest.approx(39.0)


def test_source_node_out_of_range_raises():
    grid = MeshGrid.identity(32, 32)
    with pytest.raises(IndexError):
        grid.source_node(99, 0)


def test_destination_node_returns_float_pair():
    grid = MeshGrid.identity(32, 32)
    out = grid.destination_node(1, 2)
    assert isinstance(out, tuple) and len(out) == 2
    assert isinstance(out[0], float)


def test_move_destination_node_clamps_to_canvas():
    grid = MeshGrid.identity(32, 16)
    grid.move_destination_node(1, 1, 9999, -50)
    x, y = grid.destination_node(1, 1)
    assert x == pytest.approx(31.0)
    assert y == pytest.approx(0.0)


def test_move_destination_node_out_of_range_raises():
    grid = MeshGrid.identity(32, 32)
    with pytest.raises(IndexError):
        grid.move_destination_node(99, 0, 5.0, 5.0)


# ---------------------------------------------------------------------------
# is_identity
# ---------------------------------------------------------------------------


def test_after_move_grid_no_longer_identity():
    grid = MeshGrid.identity(32, 32)
    grid.move_destination_node(1, 1, 20.0, 20.0)
    assert not grid.is_identity()


def test_tiny_perturbation_within_atol_is_identity():
    grid = MeshGrid.identity(32, 32)
    # Bump by 0.1 — under the default 0.5 px tolerance.
    grid.destination[1, 1] += 0.1
    assert grid.is_identity()


# ---------------------------------------------------------------------------
# warp_image
# ---------------------------------------------------------------------------


def test_warp_identity_returns_copy():
    img = _checker()
    grid = MeshGrid.identity(*img.shape[:2][::-1])
    out = warp_image(img, grid)
    np.testing.assert_array_equal(out, img)
    # And it's a copy — mutating the output doesn't bleed into the input.
    out[0, 0] = (99, 99, 99, 99)
    assert int(img[0, 0, 0]) != 99


def test_warp_changes_pixels_when_grid_perturbed():
    img = _checker()
    grid = MeshGrid.identity(*img.shape[:2][::-1])
    # Pull the centre destination node down + right.
    mid_r, mid_c = grid.rows // 2, grid.cols // 2
    grid.move_destination_node(mid_r, mid_c, 28.0, 28.0)
    out = warp_image(img, grid)
    assert not np.array_equal(out, img)


def test_warp_keeps_output_shape():
    img = _checker(40, 60)
    grid = MeshGrid.identity(60, 40)
    grid.move_destination_node(1, 1, 5.0, 5.0)
    out = warp_image(img, grid)
    assert out.shape == img.shape
    assert out.dtype == np.uint8


def test_warp_rejects_non_rgba():
    bad = np.zeros((32, 32, 3), dtype=np.uint8)
    grid = MeshGrid.identity(32, 32)
    with pytest.raises(ValueError):
        warp_image(bad, grid)


def test_warp_rejects_grid_shape_mismatch():
    img = _checker()
    grid = MeshGrid.identity(64, 64)
    with pytest.raises(ValueError):
        warp_image(img, grid)


def test_warp_does_not_mutate_input():
    img = _checker()
    grid = MeshGrid.identity(*img.shape[:2][::-1])
    grid.move_destination_node(1, 1, 10.0, 10.0)
    snapshot = img.copy()
    warp_image(img, grid)
    np.testing.assert_array_equal(img, snapshot)


def test_warp_min_grid_dim_documented():
    assert MIN_GRID_DIM == 2


def test_warp_max_grid_dim_documented():
    assert MAX_GRID_DIM > MIN_GRID_DIM
