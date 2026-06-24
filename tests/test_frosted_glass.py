"""Tests for the frosted-glass scatter filter."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.frosted_glass import frosted_glass


def _random(h=8, w=8, seed=0):
    arr = np.random.default_rng(seed).integers(0, 255, (h, w, 4), dtype=np.uint8)
    arr[..., 3] = 255
    return arr


def test_returns_rgba_same_shape():
    out = frosted_glass(_random(), radius=3)
    assert out.shape == (8, 8, 4)


def test_promotes_rgb_to_rgba():
    rgb = np.full((6, 6, 3), 120, dtype=np.uint8)
    assert frosted_glass(rgb, radius=2).shape == (6, 6, 4)


def test_radius_zero_is_identity():
    arr = _random()
    out = frosted_glass(arr, radius=0)
    assert np.array_equal(out, arr)


def test_deterministic_for_same_seed():
    arr = _random()
    assert np.array_equal(frosted_glass(arr, 4, seed=7), frosted_glass(arr, 4, seed=7))


def test_different_seed_changes_result():
    arr = _random()
    assert not np.array_equal(frosted_glass(arr, 4, seed=1), frosted_glass(arr, 4, seed=2))


def test_only_reuses_existing_pixels():
    arr = _random(seed=5)
    out = frosted_glass(arr, radius=3, seed=9)
    src = {tuple(p) for p in arr.reshape(-1, 4)}
    assert all(tuple(p) in src for p in out.reshape(-1, 4))


def test_uniform_image_unchanged():
    arr = np.full((8, 8, 4), 64, dtype=np.uint8)
    arr[..., 3] = 255
    assert np.array_equal(frosted_glass(arr, radius=5), arr)


def test_radius_clamped():
    arr = _random()
    out = frosted_glass(arr, radius=9999)
    assert out.shape == arr.shape


def test_does_not_mutate_input():
    arr = _random()
    before = arr.copy()
    frosted_glass(arr, radius=4)
    assert np.array_equal(arr, before)


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4"):
        frosted_glass(bad)
