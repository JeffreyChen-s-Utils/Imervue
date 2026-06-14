"""Tests for the pure deep-zoom filmstrip layout helpers.

These cover the band geometry, the centred visible-item window, the visibility
policy, the click hit-test, and the aspect-preserving fit — all without a Qt
widget or GL context. A small composition test mirrors the view's click glue to
pin the click-to-index contract end to end.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.filmstrip import (
    BAND_VPAD,
    ITEM_HEIGHT,
    ITEM_WIDTH,
    compute_filmstrip_items,
    filmstrip_band,
    filmstrip_item_at,
    fit_rect_centered,
    visible_filmstrip_items,
)


class TestFilmstripBand:
    def test_band_is_flush_with_bottom(self):
        y_top, band_h = filmstrip_band(600, 72, 8)
        assert band_h == 72 + 2 * 8
        assert y_top == 600 - band_h


class TestVisibleFilmstripItems:
    def test_empty_list(self):
        assert visible_filmstrip_items(0, 0, 500, 100, 0) == []

    def test_centres_window_on_current(self):
        # 5 items fit; current 5 of 10 → window starts at 3, current sits mid-row.
        items = visible_filmstrip_items(5, 10, 500, 100, 0)
        assert [idx for idx, _ in items] == [3, 4, 5, 6, 7]
        assert items[0][1] == 0  # full-width row → no centring slack

    def test_clamps_window_at_start(self):
        items = visible_filmstrip_items(0, 10, 500, 100, 0)
        assert [idx for idx, _ in items] == [0, 1, 2, 3, 4]

    def test_clamps_window_at_end(self):
        items = visible_filmstrip_items(9, 10, 500, 100, 0)
        assert [idx for idx, _ in items] == [5, 6, 7, 8, 9]

    def test_fewer_items_than_fit_are_centred(self):
        # 3 items, room for 5 → row is centred within the strip width.
        items = visible_filmstrip_items(1, 3, 500, 100, 0)
        assert [idx for idx, _ in items] == [0, 1, 2]
        assert items[0][1] == pytest.approx((500 - 300) / 2)

    def test_spacing_offsets_and_centres(self):
        items = visible_filmstrip_items(2, 5, 560, 100, 10)
        # step 110, 5 fit (550 ≤ 560); total 540 → x0 == 10, then +110 each.
        assert [round(x, 3) for _, x in items] == [10, 120, 230, 340, 450]

    def test_out_of_range_current_is_clamped(self):
        items = visible_filmstrip_items(99, 5, 500, 100, 0)
        assert [idx for idx, _ in items] == [0, 1, 2, 3, 4]


class TestComputeFilmstripItems:
    def _kwargs(self, **over):
        base = dict(enabled=True, in_grid_mode=False, current_index=2,
                    count=5, strip_width=2000)
        base.update(over)
        return base

    def test_disabled_returns_empty(self):
        assert compute_filmstrip_items(**self._kwargs(enabled=False)) == []

    def test_grid_mode_returns_empty(self):
        assert compute_filmstrip_items(**self._kwargs(in_grid_mode=True)) == []

    @pytest.mark.parametrize("count", [0, 1])
    def test_single_or_empty_returns_empty(self, count):
        assert compute_filmstrip_items(**self._kwargs(count=count)) == []

    def test_valid_state_lays_items_out(self):
        items = compute_filmstrip_items(**self._kwargs())
        assert len(items) == 5
        assert [idx for idx, _ in items] == [0, 1, 2, 3, 4]
        assert all(isinstance(x, float) for _, x in items)


class TestFilmstripItemAt:
    ITEMS = [(0, 0.0), (1, 100.0), (2, 200.0)]
    WIDTH = 90  # leaves a 10 px gap between cells

    def test_hit_first_item(self):
        assert filmstrip_item_at(45, 550, self.ITEMS, self.WIDTH, 512, 600) == 0

    def test_hit_middle_item(self):
        assert filmstrip_item_at(150, 550, self.ITEMS, self.WIDTH, 512, 600) == 1

    def test_gap_between_items_is_miss(self):
        assert filmstrip_item_at(95, 550, self.ITEMS, self.WIDTH, 512, 600) is None

    def test_click_above_band_is_miss(self):
        assert filmstrip_item_at(45, 500, self.ITEMS, self.WIDTH, 512, 600) is None

    def test_click_below_view_is_miss(self):
        assert filmstrip_item_at(45, 601, self.ITEMS, self.WIDTH, 512, 600) is None


class TestFitRectCentered:
    def test_wide_content_letterboxes_vertically(self):
        assert fit_rect_centered(200, 100, 0, 0, 100, 100) == (0, 25, 100, 50)

    def test_tall_content_pillarboxes_horizontally(self):
        assert fit_rect_centered(100, 200, 10, 20, 100, 100) == (35, 20, 50, 100)

    def test_small_content_upscales_to_fill(self):
        # Low-res preview: a tiny thumbnail scales up to fill the box.
        assert fit_rect_centered(50, 50, 0, 0, 100, 100) == (0, 0, 100, 100)

    def test_degenerate_content_falls_back_to_box(self):
        assert fit_rect_centered(0, 0, 5, 6, 100, 80) == (5, 6, 100, 80)


def _resolve_click(x, y, *, enabled, in_grid_mode, current_index, count,
                   strip_width, view_height):
    """Mirror ``GPUImageView._filmstrip_item_at`` to pin the composed contract."""
    items = compute_filmstrip_items(
        enabled=enabled, in_grid_mode=in_grid_mode, current_index=current_index,
        count=count, strip_width=strip_width,
    )
    if not items:
        return None
    y_top, _ = filmstrip_band(view_height, ITEM_HEIGHT, BAND_VPAD)
    return filmstrip_item_at(x, y, items, ITEM_WIDTH, y_top, view_height)


class TestClickResolution:
    def test_click_on_current_thumbnail_returns_its_index(self):
        # strip 1000, count 10, current 5 → 9 items from index 1; current is the
        # 5th cell at x≈448; click inside it resolves back to index 5.
        idx = _resolve_click(498, 550, enabled=True, in_grid_mode=False,
                             current_index=5, count=10, strip_width=1000,
                             view_height=600)
        assert idx == 5

    def test_click_above_band_returns_none(self):
        idx = _resolve_click(498, 400, enabled=True, in_grid_mode=False,
                             current_index=5, count=10, strip_width=1000,
                             view_height=600)
        assert idx is None

    def test_disabled_returns_none(self):
        idx = _resolve_click(498, 550, enabled=False, in_grid_mode=False,
                             current_index=5, count=10, strip_width=1000,
                             view_height=600)
        assert idx is None
