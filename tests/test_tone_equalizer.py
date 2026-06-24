"""Tests for the per-zone tone equalizer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.tone_equalizer import (
    apply_tone_equalizer,
    zone_gain_map,
)

_RGBA = 4


def _grey(value, alpha=255, size=(8, 8)):
    arr = np.full((size[0], size[1], _RGBA), value, dtype=np.uint8)
    arr[..., 3] = alpha
    return arr


# ---------------------------------------------------------------------------
# zone_gain_map
# ---------------------------------------------------------------------------


def test_gain_map_constant_zones_is_flat():
    lum = np.linspace(0.0, 1.0, 16, dtype=np.float32).reshape(4, 4)
    gain = zone_gain_map(lum, (1.0, 1.0, 1.0))
    # Every zone gains one stop -> the whole map is one stop regardless of tone.
    assert np.allclose(gain, 1.0, atol=1e-4)


def test_gain_map_highlights_only_spares_shadows():
    shadow = np.full((2, 2), 0.02, dtype=np.float32)   # ~ -5.6 EV
    highlight = np.full((2, 2), 1.0, dtype=np.float32)  # 0 EV
    gains = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0)  # only the top zone lifts
    assert zone_gain_map(shadow, gains).mean() < 0.1
    assert zone_gain_map(highlight, gains).mean() == pytest.approx(2.0, abs=1e-4)


def test_gain_map_interpolates_between_zones():
    # A luminance halfway (in EV) between two zones gets the average gain.
    gains = (0.0, 2.0)  # zone at -8 EV = 0, zone at 0 EV = 2
    mid = np.full((1, 1), 2.0 ** -4.0, dtype=np.float32)  # -4 EV, the midpoint
    assert zone_gain_map(mid, gains)[0, 0] == pytest.approx(1.0, abs=1e-3)


def test_gain_map_clamps_extreme_gains():
    gain = zone_gain_map(np.full((1, 1), 1.0, dtype=np.float32), (0.0, 99.0))
    assert gain[0, 0] == pytest.approx(4.0, abs=1e-4)  # clamped to the limit


# ---------------------------------------------------------------------------
# apply_tone_equalizer
# ---------------------------------------------------------------------------


def test_apply_all_zero_is_identity():
    arr = _grey(128)
    out = apply_tone_equalizer(arr, (0.0, 0.0, 0.0))
    assert np.array_equal(out, arr)


def test_apply_uniform_lift_brightens():
    arr = _grey(100)
    out = apply_tone_equalizer(arr, (1.0, 1.0, 1.0), smoothing=0)
    # Flat one-stop lift doubles the value: 100 -> 200.
    assert int(out[0, 0, 0]) == pytest.approx(200, abs=2)


def test_apply_uniform_cut_darkens():
    arr = _grey(200)
    out = apply_tone_equalizer(arr, (-1.0, -1.0, -1.0), smoothing=0)
    assert int(out[0, 0, 0]) == pytest.approx(100, abs=2)


def test_apply_zone_selectivity_leaves_other_tones():
    # Lift only the highlight zone; a mid-grey patch should barely move.
    arr = _grey(128)
    gains = (0.0,) * 8 + (2.0,)
    out = apply_tone_equalizer(arr, gains, smoothing=0)
    assert abs(int(out[0, 0, 0]) - 128) < 30


def test_apply_preserves_alpha():
    arr = _grey(120, alpha=140)
    out = apply_tone_equalizer(arr, (1.0, 1.0), smoothing=0)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_apply_does_not_mutate_input():
    arr = _grey(120)
    before = arr.copy()
    apply_tone_equalizer(arr, (1.0, -1.0, 1.0), smoothing=0)
    assert np.array_equal(arr, before)


def test_apply_smoothing_runs_without_error():
    arr = _grey(120)
    out = apply_tone_equalizer(arr, (1.0, 1.0, 1.0), smoothing=4)
    assert out.shape == arr.shape


def test_apply_rejects_too_few_zones():
    with pytest.raises(ValueError, match="at least two"):
        apply_tone_equalizer(_grey(120), (1.0,))


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5, 4), dtype=np.float32),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_apply_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4 uint8"):
        apply_tone_equalizer(bad, (1.0, 1.0))
