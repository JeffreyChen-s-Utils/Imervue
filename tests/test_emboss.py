"""Tests for the emboss relief filter."""
from __future__ import annotations

import math

import numpy as np
import pytest

from Imervue.image.emboss import apply_emboss, emboss_shade

_RGBA = 4


def _grey(value, alpha=255, size=(8, 8)):
    arr = np.full((size[0], size[1], _RGBA), value, dtype=np.uint8)
    arr[..., 3] = alpha
    return arr


# ---------------------------------------------------------------------------
# emboss_shade
# ---------------------------------------------------------------------------


def test_flat_field_shades_to_sin_elevation():
    height = np.full((6, 6), 0.5, dtype=np.float32)
    shade = emboss_shade(height, azimuth_deg=135.0, elevation_deg=30.0, depth=1.0)
    # No gradient -> normal is straight up -> shade equals the light's sin(elev).
    assert np.allclose(shade, math.sin(math.radians(30.0)), atol=1e-4)


def test_depth_zero_ignores_content():
    height = np.linspace(0.0, 1.0, 36, dtype=np.float32).reshape(6, 6)
    shade = emboss_shade(height, azimuth_deg=90.0, elevation_deg=45.0, depth=0.0)
    assert np.allclose(shade, math.sin(math.radians(45.0)), atol=1e-4)


def test_edge_creates_light_and_dark_sides():
    height = np.zeros((4, 6), dtype=np.float32)
    height[:, 3:] = 1.0  # a vertical step in the middle
    shade = emboss_shade(height, azimuth_deg=0.0, elevation_deg=20.0, depth=4.0)
    # The lit and shadowed sides of the step must differ from the flat baseline.
    assert shade.min() < shade.max()


def test_shade_in_unit_range():
    height = np.random.default_rng(0).random((8, 8)).astype(np.float32)
    shade = emboss_shade(height, azimuth_deg=200.0, elevation_deg=60.0, depth=6.0)
    assert shade.min() >= 0.0 and shade.max() <= 1.0


def test_depth_clamped():
    height = np.linspace(0.0, 1.0, 16, dtype=np.float32).reshape(4, 4)
    shade = emboss_shade(height, azimuth_deg=45.0, elevation_deg=45.0, depth=999.0)
    assert shade.min() >= 0.0 and shade.max() <= 1.0


# ---------------------------------------------------------------------------
# apply_emboss
# ---------------------------------------------------------------------------


def test_apply_grayscale_output_is_neutral():
    arr = _grey(180)
    out = apply_emboss(arr, grayscale=True)
    assert np.array_equal(out[..., 0], out[..., 1])
    assert np.array_equal(out[..., 1], out[..., 2])


def test_apply_flat_image_is_uniform_grey():
    arr = _grey(180)
    out = apply_emboss(arr, azimuth_deg=135.0, elevation_deg=90.0, depth=1.0)
    # Light straight overhead on a flat field -> shade 1 -> white relief.
    assert int(out[0, 0, 0]) == pytest.approx(255, abs=1)
    assert np.ptp(out[..., 0]) == 0


def test_apply_colour_mode_modulates_original():
    arr = _grey(200)
    arr[..., 0] = 240  # tint it
    out = apply_emboss(arr, grayscale=False, elevation_deg=90.0, depth=1.0)
    # Colour mode keeps channel ratios (here red stays the brightest channel).
    assert int(out[0, 0, 0]) >= int(out[0, 0, 1])


def test_apply_preserves_alpha():
    arr = _grey(180, alpha=120)
    out = apply_emboss(arr)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_apply_does_not_mutate_input():
    arr = _grey(180)
    before = arr.copy()
    apply_emboss(arr, depth=4.0)
    assert np.array_equal(arr, before)


def test_apply_accepts_rgb_without_alpha():
    arr = np.full((6, 6, 3), 180, dtype=np.uint8)
    out = apply_emboss(arr)
    assert out.shape == arr.shape


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5, 4), dtype=np.float32),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_apply_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4 uint8"):
        apply_emboss(bad)
