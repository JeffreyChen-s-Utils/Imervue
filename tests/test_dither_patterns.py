"""Tests for ordered (Bayer) dithering."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.dither_patterns import (
    apply_ordered_dither,
    bayer_matrix,
    threshold_map,
)


# ---------------------------------------------------------------------------
# bayer_matrix
# ---------------------------------------------------------------------------


def test_bayer_order_1_is_base():
    assert np.allclose(bayer_matrix(1), [[0.0, 0.5], [0.75, 0.25]])


def test_bayer_shape_and_range():
    m = bayer_matrix(3)
    assert m.shape == (8, 8)
    assert m.min() >= 0.0
    assert m.max() < 1.0


def test_bayer_cells_are_distinct():
    m = bayer_matrix(2)
    assert len(np.unique(m)) == m.size  # all 16 thresholds distinct


def test_bayer_invalid_order_raises():
    with pytest.raises(ValueError, match="order must be"):
        bayer_matrix(0)


# ---------------------------------------------------------------------------
# threshold_map
# ---------------------------------------------------------------------------


def test_threshold_map_shape_and_tiling():
    tmap = threshold_map(10, 7, order=1)
    assert tmap.shape == (10, 7)
    # Tiles the 2x2 base, so (0,0) == (2,2).
    assert tmap[0, 0] == tmap[2, 2]


# ---------------------------------------------------------------------------
# apply_ordered_dither
# ---------------------------------------------------------------------------


def _gray_rgba(value, alpha=255, size=8):
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[..., :3] = value
    arr[..., 3] = alpha
    return arr


def test_two_levels_outputs_only_black_and_white():
    out = apply_ordered_dither(_gray_rgba(128), levels=2)
    unique = set(np.unique(out[..., :3]).tolist())
    assert unique <= {0, 255}
    assert unique == {0, 255}  # a mid grey dithers to a mix of both


def test_pure_black_stays_black():
    out = apply_ordered_dither(_gray_rgba(0), levels=2)
    assert np.all(out[..., :3] == 0)


def test_pure_white_stays_white():
    out = apply_ordered_dither(_gray_rgba(255), levels=2)
    assert np.all(out[..., :3] == 255)


def test_alpha_preserved():
    out = apply_ordered_dither(_gray_rgba(120, alpha=200), levels=4)
    assert np.all(out[..., 3] == 200)


def test_more_levels_stays_closer_to_original():
    src = _gray_rgba(100)
    coarse = apply_ordered_dither(src, levels=2)
    fine = apply_ordered_dither(src, levels=16)
    coarse_err = np.abs(coarse[..., :3].astype(int) - 100).mean()
    fine_err = np.abs(fine[..., :3].astype(int) - 100).mean()
    assert fine_err < coarse_err


def test_does_not_mutate_input():
    src = _gray_rgba(128)
    before = src.copy()
    apply_ordered_dither(src, levels=2)
    assert np.array_equal(src, before)


def test_invalid_levels_raises():
    with pytest.raises(ValueError, match="levels must be"):
        apply_ordered_dither(_gray_rgba(128), levels=1)


@pytest.mark.parametrize("bad", [
    np.zeros((8, 8, 3), dtype=np.uint8),
    np.zeros((8, 8, 4), dtype=np.float32),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx4 uint8"):
        apply_ordered_dither(bad)
