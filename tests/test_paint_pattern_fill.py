"""Tests for pattern fill / tiling."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.pattern_fill import render_pattern_fill


def _solid_canvas(rgb=(255, 255, 255), h=20, w=20):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., :3] = rgb
    img[..., 3] = 255
    return img


def _checker_pattern(size=4):
    """Tiny black/white checkerboard pattern."""
    pat = np.zeros((size, size, 4), dtype=np.uint8)
    pat[..., 3] = 255
    for y in range(size):
        for x in range(size):
            if (x + y) % 2 == 0:
                pat[y, x, :3] = (0, 0, 0)
            else:
                pat[y, x, :3] = (255, 255, 255)
    return pat


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


def test_pattern_fill_returns_true_when_painting():
    canvas = _solid_canvas()
    pattern = _checker_pattern()
    assert render_pattern_fill(canvas, pattern) is True


def test_pattern_fill_zero_opacity_returns_false():
    canvas = _solid_canvas()
    pattern = _checker_pattern()
    snapshot = canvas.copy()
    assert render_pattern_fill(canvas, pattern, opacity=0.0) is False
    np.testing.assert_array_equal(canvas, snapshot)


def test_pattern_fill_rejects_non_rgba_canvas():
    canvas = np.zeros((10, 10, 3), dtype=np.uint8)
    pattern = _checker_pattern()
    with pytest.raises(ValueError, match="canvas must be HxWx4"):
        render_pattern_fill(canvas, pattern)


def test_pattern_fill_rejects_non_rgba_pattern():
    canvas = _solid_canvas()
    pattern = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="pattern must be HxWx4"):
        render_pattern_fill(canvas, pattern)


def test_pattern_fill_rejects_oversized_scale():
    canvas = _solid_canvas()
    pattern = _checker_pattern()
    with pytest.raises(ValueError, match="scale"):
        render_pattern_fill(canvas, pattern, scale=999.0)


def test_pattern_fill_rejects_undersized_scale():
    canvas = _solid_canvas()
    pattern = _checker_pattern()
    with pytest.raises(ValueError, match="scale"):
        render_pattern_fill(canvas, pattern, scale=0.001)


# ---------------------------------------------------------------------------
# Tiling
# ---------------------------------------------------------------------------


def test_pattern_fill_tiles_across_canvas():
    """A 4×4 pattern on a 20×20 canvas should produce checker-style
    output spanning the whole canvas."""
    canvas = _solid_canvas()
    pattern = _checker_pattern(size=4)
    render_pattern_fill(canvas, pattern)
    # Pixel (0, 0) is black (pattern (0, 0)).
    assert tuple(canvas[0, 0, :3]) == (0, 0, 0)
    # Pixel (4, 0) wraps back to pattern (0, 0) → black.
    assert tuple(canvas[0, 4, :3]) == (0, 0, 0)
    # Pixel (1, 0) is white (pattern (1, 0)).
    assert tuple(canvas[0, 1, :3]) == (255, 255, 255)


def test_pattern_fill_offset_shifts_tiling_origin():
    canvas = _solid_canvas()
    pattern = _checker_pattern(size=4)
    # offset=(1, 0) shifts pattern right by 1 — pixel (0, 0) now
    # samples pattern (3, 0) which is white.
    render_pattern_fill(canvas, pattern, offset=(1, 0))
    assert tuple(canvas[0, 0, :3]) == (255, 255, 255)


def test_pattern_fill_negative_offset():
    canvas = _solid_canvas()
    pattern = _checker_pattern(size=4)
    # offset=(-1, 0) shifts left — pixel (0, 0) samples pattern (1, 0).
    render_pattern_fill(canvas, pattern, offset=(-1, 0))
    assert tuple(canvas[0, 0, :3]) == (255, 255, 255)


def test_pattern_fill_scale_resizes_tiles():
    """With scale=2, the pattern doubles — checker squares are now
    2×2, so pixels (0, 0) and (1, 0) should both be black."""
    canvas = _solid_canvas()
    pattern = _checker_pattern(size=2)   # 2x2: black, white, white, black
    render_pattern_fill(canvas, pattern, scale=2.0)
    # Pattern doubles to 4x4 with each original pixel becoming a 2x2
    # block. Pattern (0, 0) is black → pixels (0, 0) and (0, 1) black.
    assert tuple(canvas[0, 0, :3]) == (0, 0, 0)
    assert tuple(canvas[0, 1, :3]) == (0, 0, 0)


def test_pattern_fill_respects_selection():
    canvas = _solid_canvas()
    pattern = _checker_pattern()
    # Only paint left half.
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[:, :10] = True
    render_pattern_fill(canvas, pattern, selection=sel)
    # Right half stays untouched (white).
    assert tuple(canvas[5, 15, :3]) == (255, 255, 255)
    # Left half has pattern.
    assert tuple(canvas[0, 0, :3]) == (0, 0, 0)


def test_pattern_fill_empty_selection_returns_false():
    canvas = _solid_canvas()
    pattern = _checker_pattern()
    sel = np.zeros((20, 20), dtype=np.bool_)
    snapshot = canvas.copy()
    assert render_pattern_fill(canvas, pattern, selection=sel) is False
    np.testing.assert_array_equal(canvas, snapshot)


def test_pattern_fill_rejects_selection_shape_mismatch():
    canvas = _solid_canvas(h=20, w=20)
    pattern = _checker_pattern()
    bad_sel = np.zeros((10, 10), dtype=np.bool_)
    with pytest.raises(ValueError, match="does not match"):
        render_pattern_fill(canvas, pattern, selection=bad_sel)


def test_pattern_fill_rejects_non_bool_selection():
    canvas = _solid_canvas()
    pattern = _checker_pattern()
    sel = np.zeros((20, 20), dtype=np.uint8)
    with pytest.raises(ValueError, match="bool"):
        render_pattern_fill(canvas, pattern, selection=sel)


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------


def test_pattern_fill_rotation_changes_output():
    """A rotated pattern produces different pixels than the unrotated
    version (smoke test that rotation actually runs)."""
    canvas_a = _solid_canvas()
    canvas_b = _solid_canvas()
    pattern = _checker_pattern(size=8)
    render_pattern_fill(canvas_a, pattern, rotation_deg=0.0)
    render_pattern_fill(canvas_b, pattern, rotation_deg=45.0)
    assert not np.array_equal(canvas_a, canvas_b)
