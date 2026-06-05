"""Tests for the pure tile-grid layout helpers."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.tile_layout import (
    plan_tile_size_change,
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


class TestPlanTileSizeChange:
    def test_no_images_returns_none(self):
        assert plan_tile_size_change(in_deep_zoom=False, has_images=False) == "none"
        # In-deep-zoom is irrelevant when nothing is loaded.
        assert plan_tile_size_change(in_deep_zoom=True, has_images=False) == "none"

    def test_deep_zoom_defers_rebuild(self):
        assert plan_tile_size_change(in_deep_zoom=True, has_images=True) == "defer"

    def test_grid_rebuilds_now(self):
        assert plan_tile_size_change(in_deep_zoom=False, has_images=True) == "rebuild"
