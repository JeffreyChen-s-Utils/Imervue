"""Tests for the line-art "fill every closed region" pass."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.auto_region_fill import (
    DEFAULT_THRESHOLD,
    AutoFillResult,
    auto_region_fill,
)


def _blank(h: int, w: int) -> np.ndarray:
    """A fully-opaque white HxWx4 RGBA buffer."""
    arr = np.full((h, w, 4), 255, dtype=np.uint8)
    return arr


def _line_art_box(h: int, w: int, *, frame_thickness: int = 1) -> np.ndarray:
    """An empty white sheet with a black box drawn at (1,1)-(h-2,w-2).

    Border thickness is 1 pixel so the interior of the box is one
    closed region. The outer ring of pixels (the canvas edge) is the
    "exterior" region that auto_region_fill should drop.
    """
    arr = _blank(h, w)
    arr[1, 1 : w - 1, :3] = 0
    arr[h - 2, 1 : w - 1, :3] = 0
    arr[1 : h - 1, 1, :3] = 0
    arr[1 : h - 1, w - 2, :3] = 0
    return arr


def test_auto_region_fill_paints_single_enclosed_box():
    h, w = 16, 16
    canvas = _blank(h, w)
    line_art = _line_art_box(h, w)
    result = auto_region_fill(canvas, line_art, color=(255, 0, 0))
    assert isinstance(result, AutoFillResult)
    assert not result.is_empty
    assert result.regions_filled == 1
    # Inside the box must be red, outside (border ring) must be untouched.
    assert tuple(canvas[8, 8, :3]) == (255, 0, 0)
    assert tuple(canvas[0, 0, :3]) == (255, 255, 255)


def test_auto_region_fill_skips_border_regions_by_default():
    """Without any line, every paper pixel is one big border-touching
    blob — and the default ``drop_border_regions=True`` drops it.
    Pass-through of an empty line-art buffer therefore paints nothing."""
    canvas = _blank(8, 8)
    blank = _blank(8, 8)
    result = auto_region_fill(canvas, blank, color=(0, 0, 255))
    assert result.is_empty
    assert tuple(canvas[4, 4, :3]) == (255, 255, 255)


def test_auto_region_fill_can_paint_border_when_disabled():
    """``drop_border_regions=False`` paints the exterior too — the
    fallback for line-art-free flat fills like background colour."""
    canvas = _blank(8, 8)
    blank = _blank(8, 8)
    result = auto_region_fill(
        canvas, blank, color=(0, 0, 255), drop_border_regions=False,
    )
    assert not result.is_empty
    assert result.regions_filled == 1
    assert tuple(canvas[4, 4, :3]) == (0, 0, 255)


def test_auto_region_fill_two_disjoint_boxes():
    """Two non-overlapping enclosed boxes count as two regions."""
    canvas = _blank(20, 30)
    line_art = _blank(20, 30)
    # Box A at (2..7, 2..7)
    line_art[2, 2:8, :3] = 0
    line_art[7, 2:8, :3] = 0
    line_art[2:8, 2, :3] = 0
    line_art[2:8, 7, :3] = 0
    # Box B at (10..15, 15..25)
    line_art[10, 15:26, :3] = 0
    line_art[15, 15:26, :3] = 0
    line_art[10:16, 15, :3] = 0
    line_art[10:16, 25, :3] = 0
    result = auto_region_fill(canvas, line_art, color=(0, 200, 0))
    assert result.regions_filled == 2
    # Sample one pixel inside each box.
    assert tuple(canvas[5, 5, :3]) == (0, 200, 0)
    assert tuple(canvas[12, 20, :3]) == (0, 200, 0)
    # Outside both boxes (still in the border-touching exterior).
    assert tuple(canvas[0, 0, :3]) == (255, 255, 255)


def test_auto_region_fill_min_area_drops_dust():
    """A 1-pixel "region" is dropped when min_area=4."""
    canvas = _blank(8, 8)
    line_art = _blank(8, 8)
    # Single dark pixel surrounded by paper — would be a tiny dust
    # region in its own right if we labelled paper around it; but
    # the exterior absorbs everything since there are no closed
    # contours, so this is mostly a smoke test that we don't blow up
    # on tiny inputs.
    line_art[3, 3, :3] = 0
    result = auto_region_fill(canvas, line_art, color=(255, 0, 0), min_area=4)
    assert result.is_empty


def test_auto_region_fill_threshold_clamped_to_valid_range():
    canvas = _blank(8, 8)
    line_art = _line_art_box(8, 8)
    result_low = auto_region_fill(
        canvas.copy(), line_art, color=(1, 1, 1), threshold=-50,
    )
    result_high = auto_region_fill(
        canvas, line_art, color=(1, 1, 1), threshold=999,
    )
    # threshold=0 -> no pixel counts as ink, so the whole thing is
    # one big border-touching region and nothing is filled.
    assert result_low.is_empty
    # threshold>=255 -> every paper pixel below 255 mean is ink, so
    # the white interior of the box stays as paper and gets filled.
    assert not result_high.is_empty


def test_auto_region_fill_selection_clips_output():
    """Selection mask restricts the painted area; pixels outside the
    selection are never modified, even when they fall in a kept blob."""
    h, w = 16, 16
    canvas = _blank(h, w)
    line_art = _line_art_box(h, w)
    # Allow only the left half of the box.
    selection = np.zeros((h, w), dtype=bool)
    selection[:, : w // 2] = True
    result = auto_region_fill(
        canvas, line_art, color=(0, 0, 255), selection=selection,
    )
    assert not result.is_empty
    # Left half inside the box: painted.
    assert tuple(canvas[8, 4, :3]) == (0, 0, 255)
    # Right half inside the box: untouched.
    assert tuple(canvas[8, 11, :3]) == (255, 255, 255)


def test_auto_region_fill_rejects_mismatched_shapes():
    canvas = _blank(8, 8)
    line_art = _blank(16, 16)
    with pytest.raises(ValueError, match="line_art shape"):
        auto_region_fill(canvas, line_art, color=(0, 0, 0))


def test_auto_region_fill_rejects_non_rgba_inputs():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    good = _blank(4, 4)
    with pytest.raises(ValueError, match="canvas"):
        auto_region_fill(bad, good, color=(0, 0, 0))
    with pytest.raises(ValueError, match="line_art"):
        auto_region_fill(good, bad, color=(0, 0, 0))


def test_auto_region_fill_default_threshold_constant_exposed():
    assert 0 <= DEFAULT_THRESHOLD <= 255
