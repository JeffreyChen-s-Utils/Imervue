"""Tests for the pure tile-grid layout helpers."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.tile_layout import (
    DEFAULT_THUMBNAIL_SIZE,
    VALID_THUMBNAIL_SIZES,
    clamp_grid_offset,
    is_active_thumbnail_choice,
    plan_tile_size_change,
    resolve_thumbnail_size,
    tile_grid_layout,
)


class TestTileGridLayout:
    def test_dpr_one_matches_legacy_formula(self):
        # Regression guard: on a dpr==1 screen the new helper must reproduce
        # the old ``cell = base*scale + padding`` / ``width // cell`` math so
        # the primary-monitor layout is unchanged.
        width, base, scale, padding = 1920, 512, 1.0, 8
        draw_scale, cell, cols = tile_grid_layout(width, base, scale, padding, 1.0)
        legacy_cell = base * scale + padding
        assert draw_scale == pytest.approx(scale)
        assert cell == pytest.approx(legacy_cell)
        assert cols == max(1, int(width // legacy_cell))

    def test_hidpi_halves_draw_scale_and_cell(self):
        draw_scale, cell, cols = tile_grid_layout(1920, 512, 1.0, 8, 2.0)
        assert draw_scale == pytest.approx(0.5)
        assert cell == pytest.approx(512 * 0.5 + 8 / 2)
        # Smaller cell → more columns fit than at dpr==1.
        _, _, cols_1x = tile_grid_layout(1920, 512, 1.0, 8, 1.0)
        assert cols > cols_1x

    def test_tile_scale_is_applied(self):
        draw_scale, cell, _ = tile_grid_layout(1000, 256, 2.0, 8, 1.0)
        assert draw_scale == pytest.approx(2.0)
        assert cell == pytest.approx(256 * 2.0 + 8)

    def test_narrow_width_keeps_at_least_one_column(self):
        # Viewport narrower than a single cell still yields one column.
        _, _, cols = tile_grid_layout(100, 512, 1.0, 8, 1.0)
        assert cols == 1

    @pytest.mark.parametrize("dpr", [0.0, -1.0])
    def test_non_positive_dpr_clamped_to_one(self, dpr):
        # A bad probe must not divide by zero / flip the layout.
        draw_scale, cell, cols = tile_grid_layout(1920, 512, 1.0, 8, dpr)
        ref = tile_grid_layout(1920, 512, 1.0, 8, 1.0)
        assert (draw_scale, cell, cols) == ref


class TestClampGridOffset:
    # 10 tiles, 4 cols → 3 rows (last_row = 2); cell 100, tile 90 →
    # content_height = 2*100 + 90 = 290.
    _COUNT, _COLS, _CELL, _TILE = 10, 4, 100.0, 90.0
    _CONTENT_H = 290.0

    def _clamp(self, offset, view_height):
        return clamp_grid_offset(
            offset, self._COUNT, self._COLS, self._CELL, self._TILE, view_height)

    def test_in_range_offset_is_unchanged(self):
        # Content (290) taller than the 200px viewport → -50 is a valid scroll.
        assert self._clamp(-50.0, 200) == pytest.approx(-50.0)

    def test_scroll_up_past_first_row_clamps_to_zero(self):
        # A positive offset would drop the first row below the top edge,
        # revealing empty space above the grid.
        assert self._clamp(50.0, 200) == pytest.approx(0.0)

    def test_scroll_down_past_last_row_clamps_to_bottom(self):
        # min offset = view_height - content_height = 200 - 290 = -90; the last
        # row then rests flush on the bottom edge instead of scrolling away.
        assert self._clamp(-1000.0, 200) == pytest.approx(-90.0)

    def test_exact_bottom_bound_is_kept(self):
        assert self._clamp(-90.0, 200) == pytest.approx(-90.0)

    def test_grid_shorter_than_viewport_pins_to_top(self):
        # Content 290 fits inside a 400px viewport → no scrolling; any attempt
        # to move it is pinned to offset 0 (top-aligned).
        assert self._clamp(-50.0, 400) == pytest.approx(0.0)
        assert self._clamp(30.0, 400) == pytest.approx(0.0)

    def test_empty_grid_clamps_to_zero(self):
        assert clamp_grid_offset(-999.0, 0, 4, 100.0, 90.0, 200) == pytest.approx(0.0)

    def test_non_positive_cols_treated_as_single_column(self):
        # cols=0 must not divide-by-zero; one column → 3 tiles span 3 rows.
        # content = 2*100 + 90 = 290; view 50 → min offset -240.
        assert clamp_grid_offset(-1000.0, 3, 0, 100.0, 90.0, 50) == pytest.approx(-240.0)

    def test_single_row_fitting_exactly_has_no_scroll(self):
        # 4 tiles in 4 cols → one row of height 90 in a 90px viewport.
        assert clamp_grid_offset(-10.0, 4, 4, 100.0, 90.0, 90) == pytest.approx(0.0)


class TestPlanTileSizeChange:
    def test_no_images_returns_none(self):
        assert plan_tile_size_change(in_deep_zoom=False, has_images=False) == "none"
        # In-deep-zoom is irrelevant when nothing is loaded.
        assert plan_tile_size_change(in_deep_zoom=True, has_images=False) == "none"

    def test_deep_zoom_defers_rebuild(self):
        assert plan_tile_size_change(in_deep_zoom=True, has_images=True) == "defer"

    def test_grid_rebuilds_now(self):
        assert plan_tile_size_change(in_deep_zoom=False, has_images=True) == "rebuild"


class TestResolveThumbnailSize:
    def test_none_means_full_resolution(self):
        assert resolve_thumbnail_size(None) is None

    @pytest.mark.parametrize("size", VALID_THUMBNAIL_SIZES)
    def test_valid_sizes_pass_through(self, size):
        assert resolve_thumbnail_size(size) == size

    def test_string_digits_are_coerced(self):
        # JSON round-trips ints, but a hand-edited settings file may store
        # a string — coerce it rather than reject a recoverable value.
        assert resolve_thumbnail_size("256") == 256

    @pytest.mark.parametrize("bad", [0, 999, -1, "abc", [512], 3.5])
    def test_invalid_falls_back_to_default(self, bad):
        assert resolve_thumbnail_size(bad) == DEFAULT_THUMBNAIL_SIZE

    def test_custom_default_is_honoured(self):
        assert resolve_thumbnail_size(999, default=128) == 128


class TestIsActiveThumbnailChoice:
    def test_none_sentinel_matches_full_resolution(self):
        assert is_active_thumbnail_choice("None", None) is True

    def test_none_sentinel_does_not_match_a_size(self):
        assert is_active_thumbnail_choice("None", 512) is False

    def test_int_option_matches_equal_current(self):
        assert is_active_thumbnail_choice(512, 512) is True

    def test_int_option_does_not_match_full_resolution(self):
        # The old ``size == None`` check returned False here too, but the bug
        # was the *other* direction (the "None" entry never matched).
        assert is_active_thumbnail_choice(512, None) is False

    def test_int_option_does_not_match_other_size(self):
        assert is_active_thumbnail_choice(256, 512) is False
