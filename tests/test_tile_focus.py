"""Tests for the pure thumbnail-wall keyboard-focus helpers.

These exercise the focus-cursor movement, the scroll-to-reveal math, and the
focused-tile rectangle without any Qt widget or GL context — they are the
deterministic core behind the grid's arrow-key navigation.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.tile_focus import (
    DOWN,
    LEFT,
    NO_FOCUS,
    RIGHT,
    UP,
    focus_tile_rect,
    next_focus_index,
    scroll_offset_to_reveal,
)


class TestNextFocusIndex:
    def test_empty_grid_has_no_focus(self):
        for direction in (LEFT, RIGHT, UP, DOWN):
            assert next_focus_index(NO_FOCUS, direction, cols=4, count=0) == NO_FOCUS

    @pytest.mark.parametrize("direction", [LEFT, RIGHT, UP, DOWN])
    def test_first_press_focuses_first_tile(self, direction):
        assert next_focus_index(NO_FOCUS, direction, cols=4, count=10) == 0

    def test_right_steps_forward(self):
        assert next_focus_index(0, RIGHT, cols=4, count=10) == 1

    def test_right_clamps_at_last(self):
        assert next_focus_index(9, RIGHT, cols=4, count=10) == 9

    def test_right_wraps_across_row_edge(self):
        # Flat index: right from the last column lands on the next row's first
        # tile, like a file manager. (index 3 -> 4 with cols=4.)
        assert next_focus_index(3, RIGHT, cols=4, count=10) == 4

    def test_left_steps_back(self):
        assert next_focus_index(5, LEFT, cols=4, count=10) == 4

    def test_left_clamps_at_first(self):
        assert next_focus_index(0, LEFT, cols=4, count=10) == 0

    def test_down_moves_one_row(self):
        assert next_focus_index(1, DOWN, cols=4, count=10) == 5

    def test_down_stays_when_no_tile_below(self):
        # 4 cols, 10 tiles → rows [0-3] [4-7] [8-9]. Index 7 down → 11 ≥ count,
        # and there is no tile directly below, so the cursor stays put.
        assert next_focus_index(7, DOWN, cols=4, count=10) == 7

    def test_down_into_partial_last_row(self):
        # Index 5 down → 9, a real tile in the partial last row.
        assert next_focus_index(5, DOWN, cols=4, count=10) == 9

    def test_up_moves_one_row(self):
        assert next_focus_index(5, UP, cols=4, count=10) == 1

    def test_up_stays_at_top_row(self):
        assert next_focus_index(2, UP, cols=4, count=10) == 2

    def test_out_of_range_current_resets_to_first(self):
        # A stale index (e.g. after a deletion shrank the list) snaps back to 0.
        assert next_focus_index(99, RIGHT, cols=4, count=10) == 0

    @pytest.mark.parametrize("cols", [0, -3])
    def test_non_positive_cols_treated_as_single_column(self, cols):
        assert next_focus_index(0, DOWN, cols=cols, count=5) == 1


class TestScrollOffsetToReveal:
    # Layout used below: cols=3, cell == tile_extent == 100, viewport h == 300.
    def test_visible_tile_keeps_offset(self):
        # index 4 → row 1 → top=100, bottom=200, inside [0, 300].
        assert scroll_offset_to_reveal(4, 3, 100, 100, 0, 300) == 0

    def test_tile_below_scrolls_up(self):
        # index 9 → row 3 → top=300, bottom=400 > 300; shift so bottom==300.
        assert scroll_offset_to_reveal(9, 3, 100, 100, 0, 300) == -100

    def test_tile_above_scrolls_down(self):
        # offset -250 puts row 1 at top=-150 (above the top edge); align top→0.
        assert scroll_offset_to_reveal(3, 3, 100, 100, -250, 300) == -100

    def test_no_focus_keeps_offset(self):
        assert scroll_offset_to_reveal(NO_FOCUS, 3, 100, 100, 42, 300) == 42

    def test_non_positive_cols_safe(self):
        # cols→1 → index 2 is row 2 → top=200, bottom=300, exactly fits.
        assert scroll_offset_to_reveal(2, 0, 100, 100, 0, 300) == 0


class TestFocusTileRect:
    def test_rect_for_index(self):
        # cols=3, cell=100, extent=90, offsets (10, 20). index 4 → row1 col1.
        rect = focus_tile_rect(4, 3, 100, 90, 10, 20)
        assert rect == (110, 120, 200, 210)

    def test_none_when_unfocused(self):
        assert focus_tile_rect(NO_FOCUS, 3, 100, 90, 0, 0) is None

    def test_non_positive_cols_safe(self):
        # cols→1 → index 2 is row 2 col 0.
        assert focus_tile_rect(2, 0, 100, 90, 0, 0) == (0, 200, 90, 290)
