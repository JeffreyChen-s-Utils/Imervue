"""Edge-case / correctness regressions for the pure-numpy image operations.

Groups the degenerate-input hardening (1px / empty images that used to crash on
``np.gradient`` or divide-by-zero) with two correctness fixes (the no-op Whites
slider and the clone-stamp edge crescent), since each is a small, cohesive
assertion against one image helper.
"""
from __future__ import annotations

import numpy as np
import pytest


def _rgba(h, w, value=0):
    arr = np.full((h, w, 4), value, dtype=np.uint8)
    arr[..., 3] = 255
    return arr


# --------------------------------------------------------------------------
# Whites slider was a no-op for positive values (sign bug).
# --------------------------------------------------------------------------

def test_whites_positive_brightens_highlights():
    from Imervue.image.recipe_adjustments import apply_whites_blacks
    arr = _rgba(4, 4, value=200)
    out = apply_whites_blacks(arr, whites=1.0, blacks=0.0)
    assert not np.array_equal(out, arr)          # no longer a no-op
    assert int(out[0, 0, 0]) > 200               # highlights pushed toward 255


def test_whites_zero_is_identity():
    from Imervue.image.recipe_adjustments import apply_whites_blacks
    arr = _rgba(4, 4, value=128)
    assert np.array_equal(apply_whites_blacks(arr, 0.0, 0.0), arr)


# --------------------------------------------------------------------------
# Clone stamp near an edge painted a black crescent from the zero-padded patch.
# --------------------------------------------------------------------------

def test_clone_stamp_near_edge_no_black_crescent():
    from Imervue.image.clone_stamp import CloneStamp, apply_clone_stamp
    arr = _rgba(100, 100, value=100)
    out = apply_clone_stamp(
        arr, [CloneStamp(sx=2, sy=2, dx=50, dy=50, radius=20, feather=0.5)])
    # A uniform canvas cloned onto itself must stay uniform; the padded (black)
    # portion of an edge-clipped source patch must not bleed in.
    region = out[30:71, 30:71, :3]
    assert int(region.min()) >= 95


# --------------------------------------------------------------------------
# 1px / empty images: guards instead of gradient/divide-by-zero crashes.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("shape", [(1, 10), (10, 1), (1, 1)])
def test_emboss_1px_returns_copy(shape):
    from Imervue.image.emboss import apply_emboss
    arr = _rgba(*shape)
    out = apply_emboss(arr)
    assert out.shape == arr.shape


@pytest.mark.parametrize("shape", [(1, 10), (10, 1), (1, 1)])
def test_defringe_1px_returns_copy(shape):
    from Imervue.image.defringe import apply_defringe
    arr = _rgba(*shape)
    out = apply_defringe(arr, amount=1.0)
    assert out.shape == arr.shape


@pytest.mark.parametrize("shape", [(1, 10), (10, 1), (1, 1)])
def test_polar_1px_no_crash(shape):
    from Imervue.image.polar import polar_distort
    arr = _rgba(*shape)
    assert polar_distort(arr, to_polar=True).shape[2] == 4
    assert polar_distort(arr, to_polar=False).shape[2] == 4


def test_lens_undistort_1px_returns_unchanged():
    from Imervue.image.lens_correction import _devignette, _undistort
    arr = _rgba(1, 10, value=128)
    assert np.array_equal(_undistort(arr, k1=0.1), arr)      # not a black frame
    assert np.array_equal(_devignette(arr, amount=0.5), arr)


def test_statistics_empty_image_raises_clear_error():
    from Imervue.image.statistics import histogram_csv, image_statistics
    empty = np.zeros((0, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="no pixels"):
        image_statistics(empty)
    with pytest.raises(ValueError, match="no pixels"):
        histogram_csv(empty)


# --------------------------------------------------------------------------
# Steganography: an image too small for even the 32-bit header raised a cryptic
# broadcast error for an empty message instead of "message too long".
# --------------------------------------------------------------------------

def test_hide_message_too_small_raises_clear_error():
    from Imervue.image.steganography import hide_message
    tiny = np.zeros((3, 3, 3), dtype=np.uint8)   # 27 bits < 32-bit header
    with pytest.raises(ValueError, match="too long"):
        hide_message(tiny, "")


def test_hide_reveal_roundtrip_unaffected():
    from Imervue.image.steganography import hide_message, reveal_message
    arr = np.zeros((20, 20, 3), dtype=np.uint8)
    assert reveal_message(hide_message(arr, "hello")) == "hello"
