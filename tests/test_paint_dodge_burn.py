"""Tests for the dodge & burn dab engine (``Imervue.paint.dodge_burn``).

Pure-numpy, no Qt — exercises the tonal-range helper directly and the
``dodge_burn_dab`` mutator on synthetic canvases for direction, clamping,
masking and error handling.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.dodge_burn import (
    TONAL_RANGES,
    _tonal_weight,
    dodge_burn_dab,
)


def _canvas(value: int, size: int = 8) -> np.ndarray:
    """Opaque RGBA canvas filled with a uniform grey ``value``."""
    arr = np.full((size, size, 4), 255, dtype=np.uint8)
    arr[..., :3] = value
    return arr


def _kernel(size: int = 8) -> np.ndarray:
    """Flat unit kernel covering the whole patch."""
    return np.ones((size, size), dtype=np.float32)


# ---------------------------------------------------------------------------
# _tonal_weight
# ---------------------------------------------------------------------------


def test_tonal_weight_shadows_peaks_at_black():
    weight = _tonal_weight(np.array([0.0, 0.5, 1.0], dtype=np.float32), "shadows")
    assert weight[0] == pytest.approx(1.0)
    assert weight[2] == pytest.approx(0.0)


def test_tonal_weight_highlights_peaks_at_white():
    weight = _tonal_weight(np.array([0.0, 0.5, 1.0], dtype=np.float32), "highlights")
    assert weight[0] == pytest.approx(0.0)
    assert weight[2] == pytest.approx(1.0)


def test_tonal_weight_midtones_peaks_at_grey():
    weight = _tonal_weight(np.array([0.0, 0.5, 1.0], dtype=np.float32), "midtones")
    assert weight[1] == pytest.approx(1.0)
    assert weight[0] == pytest.approx(0.0)
    assert weight[2] == pytest.approx(0.0)


def test_tonal_ranges_are_the_three_documented_bands():
    assert set(TONAL_RANGES) == {"shadows", "midtones", "highlights"}


# ---------------------------------------------------------------------------
# dodge_burn_dab — direction & identity
# ---------------------------------------------------------------------------


def test_dodge_lightens_midgray():
    canvas = _canvas(128)
    before = canvas.copy()
    rect = dodge_burn_dab(canvas, 4, 4, _kernel(), amount=0.8, range_mode="midtones")
    assert rect == (0, 0, 8, 8)
    assert canvas[..., :3].mean() > before[..., :3].mean()


def test_burn_darkens_midgray():
    canvas = _canvas(128)
    before = canvas.copy()
    dodge_burn_dab(canvas, 4, 4, _kernel(), amount=-0.8, range_mode="midtones")
    assert canvas[..., :3].mean() < before[..., :3].mean()


def test_amount_zero_is_identity():
    canvas = _canvas(128)
    before = canvas.copy()
    rect = dodge_burn_dab(canvas, 4, 4, _kernel(), amount=0.0)
    assert rect == (0, 0, 0, 0)
    assert np.array_equal(canvas, before)


# ---------------------------------------------------------------------------
# Boundary conditions — clamped tones can't escape the byte range
# ---------------------------------------------------------------------------


def test_dodge_cannot_brighten_pure_white():
    canvas = _canvas(255)
    before = canvas.copy()
    dodge_burn_dab(canvas, 4, 4, _kernel(), amount=1.0, range_mode="highlights")
    assert np.array_equal(canvas, before)


def test_burn_cannot_darken_pure_black():
    canvas = _canvas(0)
    before = canvas.copy()
    dodge_burn_dab(canvas, 4, 4, _kernel(), amount=-1.0, range_mode="shadows")
    assert np.array_equal(canvas, before)


def test_dodge_never_wraps_around_to_black():
    canvas = _canvas(250)
    dodge_burn_dab(canvas, 4, 4, _kernel(), amount=1.0, range_mode="highlights")
    # A missing clip would overflow uint8 and wrap a near-white pixel to 0.
    assert canvas[..., :3].min() >= 250


def test_amount_clamped_to_unit_range():
    over = _canvas(128)
    unit = _canvas(128)
    dodge_burn_dab(over, 4, 4, _kernel(), amount=5.0, range_mode="midtones")
    dodge_burn_dab(unit, 4, 4, _kernel(), amount=1.0, range_mode="midtones")
    assert np.array_equal(over, unit)


# ---------------------------------------------------------------------------
# Geometry — off-canvas + damage rect
# ---------------------------------------------------------------------------


def test_off_canvas_returns_empty_rect():
    canvas = _canvas(128)
    before = canvas.copy()
    rect = dodge_burn_dab(canvas, -50, -50, _kernel(), amount=0.8)
    assert rect == (0, 0, 0, 0)
    assert np.array_equal(canvas, before)


def test_damage_rect_matches_clipped_patch():
    canvas = _canvas(128, size=16)
    rect = dodge_burn_dab(canvas, 8, 8, _kernel(4), amount=0.8)
    # kernel 4 centred at 8 → origin = 8 - 2 = 6, spans [6, 10).
    assert rect == (6, 6, 4, 4)


def test_damage_rect_clamps_at_edge():
    canvas = _canvas(128, size=16)
    rect = dodge_burn_dab(canvas, 0, 0, _kernel(4), amount=0.8)
    # origin = -2, clipped to [0, 2) on both axes.
    assert rect == (0, 0, 2, 2)


# ---------------------------------------------------------------------------
# Tonal targeting
# ---------------------------------------------------------------------------


def test_shadows_range_lifts_dark_pixels_more_than_bright():
    canvas = _canvas(0)
    canvas[4:, :, :3] = 200  # bright lower half, dark upper half
    before = canvas.copy()
    dodge_burn_dab(canvas, 4, 4, _kernel(), amount=0.8, range_mode="shadows")
    dark_lift = canvas[:4, :, :3].astype(int) - before[:4, :, :3]
    bright_lift = canvas[4:, :, :3].astype(int) - before[4:, :, :3]
    assert dark_lift.mean() > bright_lift.mean()


# ---------------------------------------------------------------------------
# Selection masking + alpha preservation
# ---------------------------------------------------------------------------


def test_selection_zero_blocks_all_change():
    canvas = _canvas(128)
    before = canvas.copy()
    selection = np.zeros((8, 8), dtype=np.float32)
    dodge_burn_dab(canvas, 4, 4, _kernel(), amount=0.8, selection=selection)
    assert np.array_equal(canvas, before)


def test_selection_partial_limits_region():
    canvas = _canvas(128)
    selection = np.zeros((8, 8), dtype=np.float32)
    selection[:4, :] = 1.0  # only top half selected
    dodge_burn_dab(
        canvas, 4, 4, _kernel(), amount=0.8,
        range_mode="midtones", selection=selection,
    )
    assert canvas[:4, :, :3].mean() > 128
    assert canvas[4:, :, :3].mean() == pytest.approx(128)


def test_alpha_channel_is_untouched():
    canvas = _canvas(128)
    canvas[..., 3] = 200
    dodge_burn_dab(canvas, 4, 4, _kernel(), amount=0.8)
    assert np.all(canvas[..., 3] == 200)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["foo", "shadow", "", "Midtones"])
def test_invalid_range_raises(bad):
    canvas = _canvas(128)
    with pytest.raises(ValueError, match="range_mode"):
        dodge_burn_dab(canvas, 4, 4, _kernel(), amount=0.5, range_mode=bad)


def test_invalid_range_raises_even_off_canvas():
    canvas = _canvas(128)
    with pytest.raises(ValueError, match="range_mode"):
        dodge_burn_dab(canvas, -99, -99, _kernel(), amount=0.5, range_mode="bad")


def test_rgb_canvas_without_alpha_raises():
    canvas = np.zeros((8, 8, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="RGBA"):
        dodge_burn_dab(canvas, 4, 4, _kernel(), amount=0.5)


def test_float_canvas_raises():
    canvas = np.zeros((8, 8, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="RGBA"):
        dodge_burn_dab(canvas, 4, 4, _kernel(), amount=0.5)
