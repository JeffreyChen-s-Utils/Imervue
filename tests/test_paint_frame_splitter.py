"""Tests for the manga frame splitter."""
from __future__ import annotations

import pytest

from Imervue.paint.frame_splitter import (
    SPLIT_AXES,
    find_cell_at,
    split_layout,
    split_panel,
)
from Imervue.paint.manga_panels import PanelCell, panel_grid


# ---------------------------------------------------------------------------
# split_panel
# ---------------------------------------------------------------------------


def _cell(x=0, y=0, w=100, h=100):
    return PanelCell(x=x, y=y, w=w, h=h)


def test_split_axes_constant():
    assert set(SPLIT_AXES) == {"horizontal", "vertical"}


def test_horizontal_split_50_percent_no_gutter():
    cell = _cell(x=0, y=0, w=100, h=100)
    top, bottom = split_panel(cell, axis="horizontal", split_at=50, gutter=0)
    assert top == PanelCell(x=0, y=0, w=100, h=50)
    assert bottom == PanelCell(x=0, y=50, w=100, h=50)


def test_vertical_split_50_percent_no_gutter():
    cell = _cell(x=0, y=0, w=100, h=100)
    left, right = split_panel(cell, axis="vertical", split_at=50, gutter=0)
    assert left == PanelCell(x=0, y=0, w=50, h=100)
    assert right == PanelCell(x=50, y=0, w=50, h=100)


def test_horizontal_split_with_gutter_creates_gap():
    cell = _cell(x=0, y=0, w=100, h=100)
    top, bottom = split_panel(cell, axis="horizontal", split_at=50, gutter=10)
    # Gap of 10 pixels between top and bottom.
    assert (bottom.y - (top.y + top.h)) == 10


def test_vertical_split_with_odd_gutter_balances_pixels():
    """Odd gutter splits as half/(gutter - half) so total stays exact."""
    cell = _cell(x=0, y=0, w=100, h=100)
    left, right = split_panel(cell, axis="vertical", split_at=50, gutter=7)
    # Total used = left.w + 7 + right.w = 100 (when using cell width).
    assert left.w + (right.x - (left.x + left.w)) + right.w == 100


def test_split_off_centre_position():
    cell = _cell(x=10, y=10, w=80, h=80)
    top, bottom = split_panel(cell, axis="horizontal", split_at=30, gutter=0)
    assert top.h == 20
    assert bottom.h == 60
    assert bottom.y == 30


def test_split_at_edge_raises_horizontal():
    cell = _cell(x=0, y=0, w=100, h=100)
    with pytest.raises(ValueError, match="zero-height"):
        split_panel(cell, axis="horizontal", split_at=0, gutter=0)


def test_split_at_edge_raises_vertical():
    cell = _cell(x=0, y=0, w=100, h=100)
    with pytest.raises(ValueError, match="zero-width"):
        split_panel(cell, axis="vertical", split_at=100, gutter=0)


def test_split_unknown_axis_raises():
    cell = _cell()
    with pytest.raises(ValueError, match="unknown split axis"):
        split_panel(cell, axis="diagonal", split_at=50)


def test_split_negative_gutter_raises():
    cell = _cell()
    with pytest.raises(ValueError, match="gutter"):
        split_panel(cell, axis="horizontal", split_at=50, gutter=-1)


# ---------------------------------------------------------------------------
# split_layout
# ---------------------------------------------------------------------------


def test_split_layout_replaces_target_cell_with_two():
    layout = panel_grid(200, 200, 1, 1, gutter=0, border_width=0)
    new_layout = split_layout(
        layout, cell_index=0, axis="horizontal", split_at=100,
    )
    assert len(new_layout.cells) == 2


def test_split_layout_uses_layout_gutter_when_none():
    layout = panel_grid(200, 200, 1, 1, gutter=10, border_width=0)
    new_layout = split_layout(
        layout, cell_index=0, axis="horizontal", split_at=100,
    )
    top, bottom = new_layout.cells
    assert (bottom.y - (top.y + top.h)) == 10


def test_split_layout_explicit_gutter_overrides():
    layout = panel_grid(200, 200, 1, 1, gutter=10, border_width=0)
    new_layout = split_layout(
        layout, cell_index=0, axis="horizontal", split_at=100, gutter=4,
    )
    top, bottom = new_layout.cells
    assert (bottom.y - (top.y + top.h)) == 4


def test_split_layout_preserves_page_dimensions():
    layout = panel_grid(200, 300, 2, 2, gutter=10)
    new_layout = split_layout(
        layout, cell_index=0, axis="vertical", split_at=50,
    )
    assert new_layout.width == 200
    assert new_layout.height == 300


def test_split_layout_preserves_other_cells():
    layout = panel_grid(200, 200, 2, 2, gutter=10)
    n_before = len(layout.cells)
    new_layout = split_layout(
        layout, cell_index=0, axis="horizontal", split_at=50,
    )
    assert len(new_layout.cells) == n_before + 1


def test_split_layout_inserts_at_target_position():
    layout = panel_grid(200, 200, 1, 2, gutter=0)
    new_layout = split_layout(
        layout, cell_index=0, axis="vertical", split_at=50,
    )
    # Cell 0 split into two; cell 1 (right half of original) shifts to
    # index 2.
    assert new_layout.cells[2].w == layout.cells[1].w


def test_split_layout_out_of_range_raises():
    layout = panel_grid(200, 200, 1, 1)
    with pytest.raises(IndexError):
        split_layout(layout, cell_index=10, axis="horizontal", split_at=100)


# ---------------------------------------------------------------------------
# find_cell_at
# ---------------------------------------------------------------------------


def test_find_cell_at_returns_correct_index():
    layout = panel_grid(200, 200, 1, 2, gutter=0)
    # Left cell at x=0..100; right at x=100..200.
    assert find_cell_at(layout, 50, 100) == 0
    assert find_cell_at(layout, 150, 100) == 1


def test_find_cell_at_returns_none_for_gutter_pixel():
    layout = panel_grid(200, 200, 1, 2, gutter=20)
    # Gutter spans x = 90..110 between the two cells.
    assert find_cell_at(layout, 100, 100) is None


def test_find_cell_at_returns_none_off_canvas():
    layout = panel_grid(200, 200, 1, 1)
    assert find_cell_at(layout, 1000, 1000) is None
    assert find_cell_at(layout, -10, 50) is None
