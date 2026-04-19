"""
Unit tests for ``Imervue.library.phash``.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.library.phash import compute_phash, hamming


@pytest.fixture
def solid_png(tmp_path):
    p = tmp_path / "solid.png"
    Image.fromarray(np.full((64, 64, 3), 128, dtype=np.uint8)).save(str(p))
    return str(p)


@pytest.fixture
def noise_png(tmp_path):
    p = tmp_path / "noise.png"
    rng = np.random.default_rng(seed=1234)
    arr = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
    Image.fromarray(arr).save(str(p))
    return str(p)


class TestPhash:
    def test_returns_int(self, solid_png):
        h = compute_phash(solid_png)
        assert isinstance(h, int)
        assert 0 <= h < (1 << 64)

    def test_deterministic(self, noise_png):
        assert compute_phash(noise_png) == compute_phash(noise_png)

    def test_different_images_differ(self, solid_png, noise_png):
        assert compute_phash(solid_png) != compute_phash(noise_png)

    def test_failure_returns_none(self, tmp_path):
        missing = tmp_path / "does_not_exist.png"
        assert compute_phash(str(missing)) is None


class TestHamming:
    def test_identical(self):
        assert hamming(0xABCD, 0xABCD) == 0

    def test_single_bit_diff(self):
        assert hamming(0, 1) == 1

    def test_all_bits_diff(self):
        assert hamming(0, 0xFFFFFFFFFFFFFFFF) == 64
