"""Tests for the sponge dab engine (``Imervue.paint.sponge``).

Pure-numpy, no Qt — exercises ``sponge_dab`` on synthetic coloured
canvases for chroma direction, the luminance-preserving property of
desaturation, clamping, geometry, masking and error handling.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.sponge import sponge_dab

_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def _color_canvas(rgb=(200, 100, 50), size=8) -> np.ndarray:
    """Opaque RGBA canvas filled with a uniform colour ``rgb``."""
    arr = np.full((size, size, 4), 255, dtype=np.uint8)
    arr[..., :3] = rgb
    return arr


def _kernel(size: int = 8) -> np.ndarray:
    return np.ones((size, size), dtype=np.float32)


def _mean_chroma(arr: np.ndarray) -> float:
    rgb = arr[..., :3].astype(np.int32)
    return float((rgb.max(axis=2) - rgb.min(axis=2)).mean())


def _mean_luma(arr: np.ndarray) -> float:
    return float((arr[..., :3].astype(np.float32) * _LUMA).sum(axis=2).mean())


# ---------------------------------------------------------------------------
# Direction & identity
# ---------------------------------------------------------------------------


def test_desaturate_reduces_chroma():
    canvas = _color_canvas()
    before = _mean_chroma(canvas)
    rect = sponge_dab(canvas, 4, 4, _kernel(), amount=-0.8)
    assert rect == (0, 0, 8, 8)
    assert _mean_chroma(canvas) < before


def test_saturate_increases_chroma():
    canvas = _color_canvas()
    before = _mean_chroma(canvas)
    sponge_dab(canvas, 4, 4, _kernel(), amount=0.8)
    assert _mean_chroma(canvas) > before


def test_amount_zero_is_identity():
    canvas = _color_canvas()
    before = canvas.copy()
    rect = sponge_dab(canvas, 4, 4, _kernel(), amount=0.0)
    assert rect == (0, 0, 0, 0)
    assert np.array_equal(canvas, before)


def test_full_desaturate_yields_neutral_grey():
    canvas = _color_canvas()
    sponge_dab(canvas, 4, 4, _kernel(), amount=-1.0)
    rgb = canvas[..., :3]
    # Every pixel collapses to r == g == b (a neutral grey).
    assert np.all(rgb[..., 0] == rgb[..., 1])
    assert np.all(rgb[..., 1] == rgb[..., 2])


def test_already_grey_patch_is_identity_under_desaturate():
    canvas = _color_canvas(rgb=(120, 120, 120))
    before = canvas.copy()
    sponge_dab(canvas, 4, 4, _kernel(), amount=-0.8)
    assert np.array_equal(canvas, before)


def test_desaturate_preserves_luminance():
    canvas = _color_canvas()
    before = _mean_luma(canvas)
    sponge_dab(canvas, 4, 4, _kernel(), amount=-0.6)
    # Pivoting on luma keeps brightness fixed (±1 for byte rounding).
    assert _mean_luma(canvas) == pytest.approx(before, abs=1.0)


# ---------------------------------------------------------------------------
# Clamping & geometry
# ---------------------------------------------------------------------------


def test_amount_clamped_to_unit_range():
    over = _color_canvas()
    unit = _color_canvas()
    sponge_dab(over, 4, 4, _kernel(), amount=-5.0)
    sponge_dab(unit, 4, 4, _kernel(), amount=-1.0)
    assert np.array_equal(over, unit)


def test_saturate_stays_in_byte_range():
    canvas = _color_canvas(rgb=(250, 10, 5))
    sponge_dab(canvas, 4, 4, _kernel(), amount=1.0)
    assert canvas[..., :3].max() <= 255
    assert canvas[..., :3].min() >= 0


def test_off_canvas_returns_empty_rect():
    canvas = _color_canvas()
    before = canvas.copy()
    rect = sponge_dab(canvas, -50, -50, _kernel(), amount=-0.8)
    assert rect == (0, 0, 0, 0)
    assert np.array_equal(canvas, before)


def test_damage_rect_matches_clipped_patch():
    canvas = _color_canvas(size=16)
    rect = sponge_dab(canvas, 8, 8, _kernel(4), amount=-0.8)
    assert rect == (6, 6, 4, 4)


# ---------------------------------------------------------------------------
# Selection masking + alpha preservation
# ---------------------------------------------------------------------------


def test_selection_zero_blocks_all_change():
    canvas = _color_canvas()
    before = canvas.copy()
    selection = np.zeros((8, 8), dtype=np.float32)
    sponge_dab(canvas, 4, 4, _kernel(), amount=-0.8, selection=selection)
    assert np.array_equal(canvas, before)


def test_selection_partial_limits_region():
    canvas = _color_canvas()
    selection = np.zeros((8, 8), dtype=np.float32)
    selection[:4, :] = 1.0  # only top half selected
    sponge_dab(canvas, 4, 4, _kernel(), amount=-0.8, selection=selection)
    assert _mean_chroma(canvas[:4]) < _mean_chroma(canvas[4:])


def test_alpha_channel_is_untouched():
    canvas = _color_canvas()
    canvas[..., 3] = 200
    sponge_dab(canvas, 4, 4, _kernel(), amount=-0.8)
    assert np.all(canvas[..., 3] == 200)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_rgb_canvas_without_alpha_raises():
    canvas = np.zeros((8, 8, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="RGBA"):
        sponge_dab(canvas, 4, 4, _kernel(), amount=-0.5)


def test_float_canvas_raises():
    canvas = np.zeros((8, 8, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="RGBA"):
        sponge_dab(canvas, 4, 4, _kernel(), amount=-0.5)
