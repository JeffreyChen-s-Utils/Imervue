"""Tests for Error Level Analysis."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.ela import error_level_analysis


def _rgba(h=32, w=32):
    rng = np.random.default_rng(1)
    rgb = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_shape_and_alpha():
    out = error_level_analysis(_rgba())
    assert out.shape == (32, 32, 4)
    assert np.all(out[..., 3] == 255)
    assert out.dtype == np.uint8


def test_flat_image_has_low_error():
    flat = np.zeros((32, 32, 4), dtype=np.uint8)
    flat[..., 3] = 255
    out = error_level_analysis(flat, quality=90)
    # A perfectly flat image survives JPEG nearly intact → little error.
    assert out[..., :3].max() < 20


def test_quality_clamped():
    # Out-of-range quality must not raise.
    assert error_level_analysis(_rgba(), quality=999).shape == (32, 32, 4)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        error_level_analysis(np.zeros((8, 8), dtype=np.uint8))
