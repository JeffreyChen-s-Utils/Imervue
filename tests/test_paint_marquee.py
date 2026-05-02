"""Tests for the selection marquee edge extraction."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.marquee import bounding_rect, selection_outline_segments


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_segments_rejects_3d_mask():
    with pytest.raises(ValueError):
        selection_outline_segments(np.zeros((4, 4, 4), dtype=np.bool_))


def test_segments_rejects_non_bool_dtype():
    with pytest.raises(ValueError):
        selection_outline_segments(np.zeros((4, 4), dtype=np.uint8))


def test_segments_empty_mask_returns_zero_segments():
    out = selection_outline_segments(np.zeros((4, 4), dtype=np.bool_))
    assert out.shape == (0, 4)
    assert out.dtype == np.int32


# ---------------------------------------------------------------------------
# Boundary extraction
# ---------------------------------------------------------------------------


def test_segments_full_canvas_selection_traces_outer_border_only():
    mask = np.ones((3, 3), dtype=np.bool_)
    out = selection_outline_segments(mask)
    # 12 segments: 3 left + 3 right + 3 top + 3 bottom.
    assert out.shape[0] == 12


def test_segments_one_pixel_selection_yields_four_unit_edges():
    mask = np.zeros((4, 4), dtype=np.bool_)
    mask[1, 1] = True
    out = selection_outline_segments(mask)
    assert out.shape[0] == 4


def test_segments_2x2_block_yields_eight_unit_edges():
    mask = np.zeros((4, 4), dtype=np.bool_)
    mask[1:3, 1:3] = True
    out = selection_outline_segments(mask)
    # Eight unit segments around a 2x2 block.
    assert out.shape[0] == 8


def test_segments_corner_pixel_includes_canvas_edge():
    mask = np.zeros((3, 3), dtype=np.bool_)
    mask[0, 0] = True
    out = selection_outline_segments(mask)
    # Two interior + two outer-canvas edges = 4.
    assert out.shape[0] == 4


def test_segments_disconnected_pixels_each_get_own_outline():
    mask = np.zeros((5, 5), dtype=np.bool_)
    mask[1, 1] = True
    mask[3, 3] = True
    out = selection_outline_segments(mask)
    # 4 + 4 = 8 segments.
    assert out.shape[0] == 8


def test_segments_dtype_is_int32():
    mask = np.zeros((3, 3), dtype=np.bool_)
    mask[1, 1] = True
    out = selection_outline_segments(mask)
    assert out.dtype == np.int32


# ---------------------------------------------------------------------------
# bounding_rect
# ---------------------------------------------------------------------------


def test_bounding_rect_empty_mask_returns_none():
    assert bounding_rect(np.zeros((4, 4), dtype=np.bool_)) is None


def test_bounding_rect_single_pixel():
    mask = np.zeros((4, 4), dtype=np.bool_)
    mask[1, 2] = True
    assert bounding_rect(mask) == (2, 1, 3, 2)


def test_bounding_rect_block():
    mask = np.zeros((6, 6), dtype=np.bool_)
    mask[1:4, 2:5] = True
    assert bounding_rect(mask) == (2, 1, 5, 4)


def test_bounding_rect_rejects_wrong_dtype():
    with pytest.raises(ValueError):
        bounding_rect(np.zeros((4, 4), dtype=np.uint8))
