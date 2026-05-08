"""Tests for the transparency-checker tile builder."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.canvas import build_checker_pattern


def test_default_tile_is_two_cells_square():
    """A single tile is exactly ``cell * 2`` on each side so
    ``GL_REPEAT`` reproduces the full alternating pattern without
    visible seams when texcoords cross the tile boundary."""
    tile = build_checker_pattern(8)
    assert tile.shape == (16, 16, 4)
    assert tile.dtype == np.uint8


def test_top_left_cell_is_light_and_top_right_is_dark():
    """The standard checker convention starts with light at (0,0)
    and alternates from there. Verifies the (0..cell, 0..cell) and
    (cell..2*cell, 0..cell) cells differ."""
    tile = build_checker_pattern(4)
    light_cell = tile[0:4, 0:4]
    dark_cell = tile[0:4, 4:8]
    assert (light_cell == light_cell[0, 0]).all()
    assert (dark_cell == dark_cell[0, 0]).all()
    assert int(light_cell[0, 0, 0]) > int(dark_cell[0, 0, 0])


def test_checker_alpha_is_opaque():
    """Alpha=255 throughout — the checker is meant to be visible
    underneath transparent canvas pixels, not blended with the
    editor backdrop."""
    tile = build_checker_pattern()
    assert (tile[..., 3] == 255).all()


def test_diagonal_cells_share_color():
    """Cells across a diagonal alternate parity → same colour. This
    is the property GL_REPEAT relies on when the canvas tiles the
    16x16 pattern across a much larger canvas."""
    tile = build_checker_pattern(2)
    assert (tile[0, 0] == tile[2, 2]).all()
    assert (tile[0, 2] == tile[2, 0]).all()


def test_custom_cell_changes_grid_step():
    big = build_checker_pattern(16)
    assert big.shape == (32, 32, 4)
    # The first row is uniform inside one cell.
    assert (big[0, 0:16] == big[0, 0]).all()
    assert (big[0, 16:32] == big[0, 16]).all()
    # And the two halves differ.
    assert not (big[0, 0] == big[0, 16]).all()


def test_custom_colors_are_honored():
    tile = build_checker_pattern(
        cell=2,
        light=(10, 20, 30, 255),
        dark=(40, 50, 60, 255),
    )
    assert tuple(int(c) for c in tile[0, 0]) == (10, 20, 30, 255)
    assert tuple(int(c) for c in tile[0, 2]) == (40, 50, 60, 255)


def test_zero_cell_rejected():
    with pytest.raises(ValueError):
        build_checker_pattern(0)


def test_negative_cell_rejected():
    with pytest.raises(ValueError):
        build_checker_pattern(-4)
