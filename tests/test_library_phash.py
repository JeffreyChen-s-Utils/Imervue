"""
Unit tests for ``Imervue.library.phash``.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.library.phash import compute_phash, hamming, to_signed64


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
        first = compute_phash(noise_png)
        second = compute_phash(noise_png)
        assert first == second

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

    def test_signed_and_unsigned_operands_compare_equal(self):
        # A real-photo pHash read back from SQLite is a negative signed int;
        # comparing it against the freshly-computed unsigned twin must give 0.
        unsigned = 0xF000000000000000
        signed = to_signed64(unsigned)
        assert signed < 0
        assert hamming(unsigned, signed) == 0
        assert hamming(unsigned, 0) == hamming(signed, 0) == 4


class TestToSigned64:
    def test_low_values_unchanged(self):
        assert to_signed64(0) == 0
        assert to_signed64(42) == 42
        assert to_signed64((1 << 63) - 1) == (1 << 63) - 1

    def test_high_bit_reinterpreted_as_negative(self):
        assert to_signed64(1 << 63) == -(1 << 63)
        assert to_signed64((1 << 64) - 1) == -1

    def test_result_fits_signed_64_and_preserves_bits(self):
        for unsigned in (1 << 63, (1 << 63) | 0x1234,
                         0xAA55AA55AA55AA55, (1 << 64) - 1):
            signed = to_signed64(unsigned)
            assert -(1 << 63) <= signed < (1 << 63)
            # Identical 64-bit pattern → zero Hamming distance.
            assert hamming(unsigned, signed) == 0

    def test_real_photo_phash_exceeds_signed_range(self, noise_png):
        # Guards the premise of the fix: a non-flat image's pHash has its high
        # bit set, so the raw unsigned value would overflow SQLite unchanged.
        h = compute_phash(noise_png)
        assert h >= (1 << 63)
        assert -(1 << 63) <= to_signed64(h) < (1 << 63)
