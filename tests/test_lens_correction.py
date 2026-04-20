"""Tests for lens correction."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import lens_correction as lc


def _solid(h=32, w=40, val=120):
    arr = np.full((h, w, 4), val, dtype=np.uint8)
    arr[..., 3] = 255
    return arr


class TestIdentity:
    def test_default_options_is_identity(self):
        assert lc.LensCorrectionOptions().is_identity()

    def test_identity_returns_input(self):
        arr = _solid()
        out = lc.apply_lens_correction(arr, lc.LensCorrectionOptions())
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((10, 10, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            lc.apply_lens_correction(arr, lc.LensCorrectionOptions(k1=0.1))


class TestDistortion:
    def test_nonzero_k1_changes_output(self):
        arr = np.tile(np.arange(40, dtype=np.uint8), (32, 1))
        arr = np.dstack([arr, arr, arr, np.full_like(arr, 255)])
        out = lc.apply_lens_correction(arr, lc.LensCorrectionOptions(k1=0.3))
        assert not np.array_equal(out, arr)

    def test_centre_pixel_is_unchanged_by_distortion(self):
        arr = _solid(h=33, w=41, val=80)
        arr[16, 20, :3] = (250, 200, 150)
        out = lc.apply_lens_correction(arr, lc.LensCorrectionOptions(k1=-0.3))
        # The centre pixel should be (nearly) unchanged.
        assert abs(int(out[16, 20, 0]) - 250) <= 2


class TestVignette:
    def test_positive_vignette_brightens_corners(self):
        arr = _solid(h=32, w=32, val=100)
        out = lc.apply_lens_correction(
            arr, lc.LensCorrectionOptions(vignette=0.5),
        )
        assert out[0, 0, 0] > arr[0, 0, 0]
        # Centre should remain roughly the same.
        assert abs(int(out[16, 16, 0]) - 100) <= 2

    def test_negative_vignette_darkens_corners(self):
        arr = _solid(h=32, w=32, val=200)
        out = lc.apply_lens_correction(
            arr, lc.LensCorrectionOptions(vignette=-0.5),
        )
        assert out[0, 0, 0] < arr[0, 0, 0]


class TestChromaticAberration:
    def test_ca_shifts_red_channel_only(self):
        arr = np.zeros((32, 40, 4), dtype=np.uint8)
        arr[..., 3] = 255
        arr[:, 20:, 0] = 255  # red half on right
        arr[:, 20:, 1] = 255  # green half on right
        arr[:, 20:, 2] = 255
        out = lc.apply_lens_correction(
            arr, lc.LensCorrectionOptions(ca_red=0.01),
        )
        # Red channel should be shifted — green/blue should stay put.
        assert np.array_equal(out[..., 1], arr[..., 1])
        assert np.array_equal(out[..., 2], arr[..., 2])

    def test_alpha_preserved(self):
        arr = _solid(val=128)
        arr[..., 3] = 180
        out = lc.apply_lens_correction(
            arr, lc.LensCorrectionOptions(k1=0.1, vignette=0.2, ca_red=0.005),
        )
        assert (out[..., 3] == 180).all()
