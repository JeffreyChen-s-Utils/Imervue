"""Tests for copy-move forgery detection."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.copy_move import copy_move_map


def _rgba_from_rgb(rgb):
    alpha = np.full((*rgb.shape[:2], 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_shape_and_alpha():
    rng = np.random.default_rng(0)
    img = _rgba_from_rgb(rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8))
    out = copy_move_map(img)
    assert out.shape == (64, 64, 4)
    assert np.all(out[..., 3] == 255)


def test_uniform_image_has_no_clones():
    flat = _rgba_from_rgb(np.full((64, 64, 3), 120, dtype=np.uint8))
    out = copy_move_map(flat)
    assert not np.any(np.all(out[..., :3] == (255, 0, 0), axis=-1))


def test_duplicated_patch_is_flagged():
    rng = np.random.default_rng(1)
    rgb = np.full((96, 96, 3), 100, dtype=np.uint8)
    patch = rng.integers(0, 256, size=(16, 16, 3), dtype=np.uint8)
    rgb[8:24, 8:24] = patch
    rgb[64:80, 64:80] = patch  # an identical clone far away
    out = copy_move_map(_rgba_from_rgb(rgb))
    marked = np.all(out[..., :3] == (255, 0, 0), axis=-1)
    # Both the source and the cloned region light up.
    assert marked[8:24, 8:24].any()
    assert marked[64:80, 64:80].any()


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        copy_move_map(np.zeros((8, 8), dtype=np.uint8))
