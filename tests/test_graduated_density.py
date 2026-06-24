"""Tests for the graduated neutral-density filter."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.graduated_density import (
    apply_graduated_density,
    graduated_mask,
)


def _grey(value=128, alpha=255, size=(8, 8), channels=4):
    arr = np.full((size[0], size[1], channels), value, dtype=np.uint8)
    if channels == _RGBA:
        arr[..., 3] = alpha
    return arr


_RGBA = 4


# ---------------------------------------------------------------------------
# graduated_mask
# ---------------------------------------------------------------------------


def test_mask_shape_and_range():
    mask = graduated_mask(6, 10, angle_deg=0.0, hardness=0.5, offset=0.0)
    assert mask.shape == (6, 10)
    assert mask.min() >= 0.0 and mask.max() <= 1.0


def test_mask_horizontal_runs_top_to_bottom():
    # angle 0 darkens the top: top rows (ny=-1) are the masked (high) side.
    mask = graduated_mask(9, 4, angle_deg=0.0, hardness=0.0, offset=0.0)
    assert mask[-1, 0] < 0.5 < mask[0, 0]


def test_mask_offset_shifts_centre_line():
    base = graduated_mask(9, 4, angle_deg=0.0, hardness=0.0, offset=0.0)
    shifted = graduated_mask(9, 4, angle_deg=0.0, hardness=0.0, offset=0.5)
    # A positive offset pushes the affected region further down → less coverage.
    assert shifted.mean() < base.mean()


def test_mask_hardness_one_is_sharp():
    soft = graduated_mask(20, 4, angle_deg=0.0, hardness=0.0, offset=0.0)
    hard = graduated_mask(20, 4, angle_deg=0.0, hardness=1.0, offset=0.0)
    # A hard transition has more pixels pinned near 0 or 1 than a soft one.
    soft_mid = np.mean((soft > 0.1) & (soft < 0.9))
    hard_mid = np.mean((hard > 0.1) & (hard < 0.9))
    assert hard_mid < soft_mid


def test_mask_offset_clamped():
    # Out-of-range offset must not raise; it clamps to the [-1, 1] edge.
    mask = graduated_mask(6, 6, angle_deg=0.0, hardness=0.5, offset=9.0)
    assert mask.shape == (6, 6)


# ---------------------------------------------------------------------------
# apply_graduated_density
# ---------------------------------------------------------------------------


def test_apply_darkens_one_side_only():
    arr = _grey(200)
    out = apply_graduated_density(arr, angle_deg=0.0, density_stops=2.0, hardness=0.0)
    top = int(out[0, 0, 0])
    bottom = int(out[-1, 0, 0])
    assert top < bottom  # the masked (top) side is darker
    assert bottom == 200  # the unmasked side is untouched


def test_apply_density_stop_multiplies_exposure():
    arr = _grey(200)
    # On the fully-masked side (angle 0 + hardness 1 => sharp split at centre)
    # one stop halves the top: 200 -> ~100; the bottom is untouched.
    out = apply_graduated_density(
        arr, angle_deg=0.0, density_stops=1.0, hardness=1.0, offset=0.0,
    )
    assert int(out[0, 0, 0]) == pytest.approx(100, abs=2)
    assert int(out[-1, 0, 0]) == 200


def test_apply_negative_stops_brightens():
    arr = _grey(80)
    out = apply_graduated_density(arr, angle_deg=0.0, density_stops=-1.0, hardness=0.0)
    assert int(out[0, 0, 0]) > 80


def test_apply_preserves_alpha():
    arr = _grey(200, alpha=170)
    out = apply_graduated_density(arr, density_stops=2.0)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_apply_zero_density_no_tint_is_identity():
    arr = _grey(123)
    out = apply_graduated_density(arr, density_stops=0.0)
    assert np.array_equal(out, arr)


def test_apply_tint_pulls_channels_on_masked_side():
    arr = _grey(200)
    out = apply_graduated_density(
        arr, angle_deg=0.0, density_stops=0.0, hardness=1.0, offset=0.0,
        tint=(1.0, 1.0, 0.5),
    )
    # Fully-masked side (top): blue halved, red/green untouched.
    assert int(out[0, 0, 2]) == pytest.approx(100, abs=2)
    assert int(out[0, 0, 0]) == 200


def test_apply_density_clamped():
    arr = _grey(200)
    # Absurd stop count must clamp to the +/-8 stop limit, not overflow / raise.
    out = apply_graduated_density(arr, angle_deg=0.0, density_stops=999.0, hardness=1.0)
    assert out.dtype == np.uint8
    # 8 stops below: 200 * 2**-8 ~= 0.78 -> rounds toward 0/1, fully crushed.
    assert int(out[0, 0, 0]) <= 1


def test_apply_does_not_mutate_input():
    arr = _grey(200)
    before = arr.copy()
    apply_graduated_density(arr, density_stops=2.0)
    assert np.array_equal(arr, before)


def test_apply_accepts_rgb_without_alpha():
    arr = _grey(200, channels=3)
    out = apply_graduated_density(arr, density_stops=2.0)
    assert out.shape == arr.shape


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),       # wrong channel count
    np.zeros((4, 5, 4), dtype=np.float32),     # wrong dtype
    np.zeros((4, 5), dtype=np.uint8),          # 2-D
])
def test_apply_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4 uint8"):
        apply_graduated_density(bad)
