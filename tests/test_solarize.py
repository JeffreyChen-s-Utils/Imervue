"""Tests for the solarize tone-reversal effect."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.solarize import apply_solarize, solarize_lut


def _rgba(rgb, alpha=255, size=(4, 5)):
    arr = np.zeros((size[0], size[1], 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = alpha
    return arr


# ---------------------------------------------------------------------------
# solarize_lut
# ---------------------------------------------------------------------------


def test_lut_shape_and_dtype():
    lut = solarize_lut()
    assert lut.shape == (256,)
    assert lut.dtype == np.uint8


def test_lut_full_inversion_at_zero_threshold():
    lut = solarize_lut(threshold=0.0, mix=1.0)
    assert lut[0] == 255
    assert lut[255] == 0
    assert lut[100] == 155


def test_lut_clamps_out_of_range_params():
    # Out-of-range threshold/mix must not raise; they clamp.
    assert solarize_lut(threshold=5.0, mix=9.0).shape == (256,)
    assert solarize_lut(threshold=-1.0, mix=-1.0).shape == (256,)


def test_lut_high_threshold_keeps_low_tones():
    lut = solarize_lut(threshold=1.0, mix=1.0)  # cutoff = 255
    assert lut[128] == 128       # below cutoff: unchanged
    assert lut[255] == 0         # at cutoff: inverted


# ---------------------------------------------------------------------------
# apply_solarize
# ---------------------------------------------------------------------------


def test_apply_full_solarize_inverts_rgb():
    arr = _rgba((200, 120, 30))
    out = apply_solarize(arr, threshold=0.0, mix=1.0)
    assert np.array_equal(out[..., :3], 255 - arr[..., :3])


def test_apply_preserves_alpha():
    arr = _rgba((200, 120, 30), alpha=180)
    out = apply_solarize(arr, threshold=0.0, mix=1.0)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_apply_mix_zero_is_identity():
    arr = _rgba((200, 120, 30))
    out = apply_solarize(arr, threshold=0.0, mix=0.0)
    assert np.array_equal(out, arr)


def test_apply_does_not_mutate_input():
    arr = _rgba((200, 120, 30))
    before = arr.copy()
    apply_solarize(arr, threshold=0.2, mix=1.0)
    assert np.array_equal(arr, before)


def test_apply_partial_mix_is_between():
    arr = _rgba((200, 0, 0))
    out = apply_solarize(arr, threshold=0.0, mix=0.5)
    # halfway between 200 and its inversion 55 -> ~127/128
    assert 126 <= int(out[0, 0, 0]) <= 128


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 3), dtype=np.uint8),         # RGB, not RGBA
    np.zeros((4, 5, 4), dtype=np.float32),       # wrong dtype
    np.zeros((4, 5), dtype=np.uint8),            # 2-D
])
def test_apply_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx4 uint8"):
        apply_solarize(bad)
