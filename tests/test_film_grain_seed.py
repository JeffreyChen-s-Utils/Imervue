"""Auto-seed grain (seed=0) must vary by image content, not just dimensions.

Keying only on ``(h, w)`` gave two different same-resolution photos byte-identical
grain. A cheap content signature is now folded in.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.film_grain import _make_rng


def test_same_dims_different_content_gives_different_grain():
    a = np.zeros((64, 64, 3), dtype=np.uint8)
    b = np.full((64, 64, 3), 200, dtype=np.uint8)   # same shape, different pixels
    assert not np.array_equal(_make_rng(a, 0).random(8), _make_rng(b, 0).random(8))


def test_same_image_gives_stable_grain():
    a = np.full((32, 48, 3), 128, dtype=np.uint8)
    assert np.array_equal(_make_rng(a, 0).random(8), _make_rng(a, 0).random(8))


def test_explicit_seed_is_honoured():
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    assert np.array_equal(
        _make_rng(a, 42).random(8), np.random.default_rng(42).random(8))
