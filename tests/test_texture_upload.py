"""Tests for the GL-free RGBA preparation helper.

``prepare_rgba`` is the pure data-preparation half of the unified
texture-upload helper. The GL upload itself needs a live context and
is ``# pragma: no cover``; this module exhaustively covers the byte
preparation that three call sites used to duplicate.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.gpu_image_view.texture_upload import prepare_rgba


def test_rgb_gets_opaque_alpha_appended():
    """3-channel RGB -> 4-channel RGBA with a fully opaque alpha."""
    rgb = np.zeros((2, 3, 3), dtype=np.uint8)
    out = prepare_rgba(rgb)
    assert out.shape == (2, 3, 4)
    assert out.dtype == np.uint8
    assert np.all(out[..., 3] == 255)
    # Colour channels are preserved untouched.
    assert np.array_equal(out[..., :3], rgb)


def test_rgba_passes_through_values_unchanged():
    """Already-RGBA input keeps its exact pixel values (incl. alpha)."""
    rng = np.random.default_rng(0)
    rgba = rng.integers(0, 256, size=(4, 5, 4), dtype=np.uint8)
    out = prepare_rgba(rgba)
    assert out.shape == (4, 5, 4)
    assert np.array_equal(out, rgba)


def test_grayscale_2d_broadcasts_to_rgba():
    """2-D single-channel -> RGB broadcast + opaque alpha."""
    gray = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    out = prepare_rgba(gray)
    assert out.shape == (2, 2, 4)
    # R == G == B == original gray value.
    assert np.array_equal(out[..., 0], gray)
    assert np.array_equal(out[..., 1], gray)
    assert np.array_equal(out[..., 2], gray)
    assert np.all(out[..., 3] == 255)


def test_non_contiguous_input_becomes_contiguous():
    """A strided (non-C-contiguous) view is copied to a packed buffer."""
    base = np.zeros((4, 4, 4), dtype=np.uint8)
    view = base[::2, ::2]  # strided, non-contiguous
    assert not view.flags["C_CONTIGUOUS"]
    out = prepare_rgba(view)
    assert out.flags["C_CONTIGUOUS"]
    assert out.shape == (2, 2, 4)


def test_non_uint8_dtype_is_coerced():
    """Float / wider-int input is cast to uint8 before padding."""
    src = np.full((1, 1, 3), 200, dtype=np.float32)
    out = prepare_rgba(src)
    assert out.dtype == np.uint8
    assert out.shape == (1, 1, 4)
    assert out[0, 0, 0] == 200
    assert out[0, 0, 3] == 255


def test_int16_rgba_coerced_without_alpha_padding():
    """Wider-int RGBA is coerced to uint8 but keeps 4 channels."""
    src = np.full((2, 2, 4), 128, dtype=np.int16)
    out = prepare_rgba(src)
    assert out.dtype == np.uint8
    assert out.shape == (2, 2, 4)
    assert np.all(out == 128)


def test_single_pixel_rgb():
    """Boundary: a 1x1 RGB tile still gets a correct RGBA result."""
    out = prepare_rgba(np.array([[[1, 2, 3]]], dtype=np.uint8))
    assert out.shape == (1, 1, 4)
    assert list(out[0, 0]) == [1, 2, 3, 255]


def test_unsupported_channel_count_raises():
    """2-channel (LA-style) input is outside the documented 1/3/4 set."""
    with pytest.raises(ValueError, match="1/3/4 channels"):
        prepare_rgba(np.zeros((2, 2, 2), dtype=np.uint8))


def test_already_uint8_rgba_is_not_needlessly_copied_dtype():
    """uint8 RGBA short-circuits the dtype cast (still returns uint8)."""
    rgba = np.zeros((3, 3, 4), dtype=np.uint8)
    out = prepare_rgba(rgba)
    assert out.dtype == np.uint8
    assert out.shape == (3, 3, 4)
