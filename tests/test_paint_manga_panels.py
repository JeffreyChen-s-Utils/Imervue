"""Tests for the manga panel layout helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.manga_panels import (
    PanelCell,
    PanelLayout,
    draw_panel_borders,
    panel_grid,
    panel_rows,
)


# ---------------------------------------------------------------------------
# panel_grid — happy paths
# ---------------------------------------------------------------------------


def test_panel_grid_2x2_yields_four_cells():
    layout = panel_grid(200, 200, 2, 2, gutter=10, border_width=2)
    assert len(layout.cells) == 4
    assert layout.width == 200
    assert layout.height == 200


def test_panel_grid_cells_are_in_reading_order():
    layout = panel_grid(200, 200, 2, 2, gutter=10)
    # First cell is top-left, last is bottom-right.
    first, *_, last = layout.cells
    assert first.x < last.x
    assert first.y < last.y


def test_panel_grid_cells_are_equal_sized_within_a_grid():
    layout = panel_grid(200, 200, 2, 2, gutter=10)
    widths = {c.w for c in layout.cells}
    heights = {c.h for c in layout.cells}
    assert len(widths) == 1
    assert len(heights) == 1


def test_panel_grid_gutter_separates_cells():
    layout = panel_grid(200, 200, 1, 2, gutter=20)
    left, right = layout.cells
    horizontal_gap = right.x - (left.x + left.w)
    assert horizontal_gap == 20


def test_panel_grid_margin_offsets_first_cell():
    layout = panel_grid(200, 200, 1, 1, gutter=0, margin=15)
    cell = layout.cells[0]
    assert cell.x == 15
    assert cell.y == 15
    assert cell.w == 200 - 30
    assert cell.h == 200 - 30


def test_panel_grid_1x1_returns_single_full_cell():
    layout = panel_grid(120, 80, 1, 1, gutter=0, border_width=0)
    assert layout.cells == (PanelCell(x=0, y=0, w=120, h=80),)


def test_panel_grid_records_gutter_and_border_width():
    layout = panel_grid(200, 200, 2, 2, gutter=11, border_width=5)
    assert layout.gutter == 11
    assert layout.border_width == 5


# ---------------------------------------------------------------------------
# panel_grid — error paths
# ---------------------------------------------------------------------------


def test_panel_grid_rejects_zero_rows():
    with pytest.raises(ValueError, match="positive"):
        panel_grid(200, 200, 0, 2)


def test_panel_grid_rejects_negative_cols():
    with pytest.raises(ValueError, match="positive"):
        panel_grid(200, 200, 2, -1)


def test_panel_grid_rejects_negative_dimensions():
    with pytest.raises(ValueError, match="positive"):
        panel_grid(-100, 200, 2, 2)


def test_panel_grid_rejects_negative_gutter():
    with pytest.raises(ValueError, match=">=0"):
        panel_grid(200, 200, 2, 2, gutter=-5)


def test_panel_grid_rejects_oversized_gutter():
    """A gutter so big that a cell width / height collapses to 0."""
    with pytest.raises(ValueError, match="too large"):
        panel_grid(50, 50, 2, 2, gutter=200)


def test_panel_grid_rejects_oversized_margin():
    with pytest.raises(ValueError, match="too small"):
        panel_grid(40, 40, 1, 1, margin=30)


# ---------------------------------------------------------------------------
# panel_rows — irregular layouts
# ---------------------------------------------------------------------------


def test_panel_rows_irregular_layout_counts_cells():
    layout = panel_rows(300, 300, [1, 2, 1], gutter=10)
    assert len(layout.cells) == 4


def test_panel_rows_each_row_has_equal_height():
    layout = panel_rows(300, 300, [1, 2, 1], gutter=10)
    heights_per_row = [layout.cells[0].h, layout.cells[1].h, layout.cells[3].h]
    assert len(set(heights_per_row)) == 1


def test_panel_rows_wide_row_spans_full_width():
    layout = panel_rows(300, 300, [1, 2], gutter=10, margin=0)
    full_row = layout.cells[0]   # the [1] row
    assert full_row.x == 0
    assert full_row.w == 300


def test_panel_rows_two_cell_row_widths_differ_from_full_row():
    layout = panel_rows(300, 300, [1, 2], gutter=10)
    full_row = layout.cells[0]
    left, right = layout.cells[1], layout.cells[2]
    assert left.w < full_row.w
    assert left.w + 10 + right.w == full_row.w


def test_panel_rows_rejects_empty_specs():
    with pytest.raises(ValueError, match="at least one row"):
        panel_rows(200, 200, [])


def test_panel_rows_rejects_zero_in_row_spec():
    with pytest.raises(ValueError, match=">=1 cells"):
        panel_rows(200, 200, [1, 0, 1])


def test_panel_rows_rejects_oversized_horizontal_gutter():
    """A row with many cells + a huge gutter should fail loudly."""
    with pytest.raises(ValueError, match="row 0"):
        panel_rows(50, 200, [3], gutter=100)


# ---------------------------------------------------------------------------
# draw_panel_borders
# ---------------------------------------------------------------------------


@pytest.fixture
def white_canvas():
    return np.full((100, 100, 4), 255, dtype=np.uint8)


def test_draw_panel_borders_stamps_along_cell_edges(white_canvas):
    layout = panel_grid(100, 100, 1, 1, gutter=0, border_width=2)
    draw_panel_borders(white_canvas, layout, color=(0, 0, 0))
    # Top-left corner pixel should be black.
    assert tuple(white_canvas[0, 0]) == (0, 0, 0, 255)
    # Far interior should still be white.
    assert tuple(white_canvas[50, 50]) == (255, 255, 255, 255)


def test_draw_panel_borders_leaves_gutter_untouched(white_canvas):
    """Pixels in the gutter between two cells must stay unmodified."""
    layout = panel_grid(100, 100, 1, 2, gutter=20, border_width=2)
    draw_panel_borders(white_canvas, layout, color=(0, 0, 0))
    # First cell ends at x = 40 ((100 - 20) / 2). Gutter spans
    # x = 40..60. Pixel at (50, 50) should remain white.
    assert tuple(white_canvas[50, 50]) == (255, 255, 255, 255)


def test_draw_panel_borders_zero_width_is_noop(white_canvas):
    layout = panel_grid(100, 100, 2, 2, gutter=10, border_width=0)
    draw_panel_borders(white_canvas, layout)
    np.testing.assert_array_equal(
        white_canvas, np.full_like(white_canvas, 255),
    )


def test_draw_panel_borders_uses_supplied_color(white_canvas):
    layout = panel_grid(100, 100, 1, 1, gutter=0, border_width=3)
    draw_panel_borders(white_canvas, layout, color=(200, 50, 30))
    assert tuple(white_canvas[0, 0]) == (200, 50, 30, 255)


def test_draw_panel_borders_clips_off_canvas_cells(white_canvas):
    """A cell that pokes outside the canvas must not raise; the
    visible portion still gets a border."""
    layout = PanelLayout(
        width=100, height=100,
        cells=(PanelCell(x=80, y=80, w=50, h=50),),
        gutter=0, border_width=2,
    )
    draw_panel_borders(white_canvas, layout, color=(0, 0, 0))
    # In-canvas part of the right border (x=99) should be black.
    assert tuple(white_canvas[90, 99]) == (0, 0, 0, 255)


def test_draw_panel_borders_rejects_non_rgba_canvas():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    layout = panel_grid(10, 10, 1, 1, gutter=0, border_width=1)
    with pytest.raises(ValueError, match="HxWx4"):
        draw_panel_borders(rgb, layout)


def test_draw_panel_borders_rejects_wrong_dtype():
    canvas_f32 = np.zeros((10, 10, 4), dtype=np.float32)
    layout = panel_grid(10, 10, 1, 1, gutter=0, border_width=1)
    with pytest.raises(ValueError, match="HxWx4"):
        draw_panel_borders(canvas_f32, layout)
