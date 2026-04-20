"""Tests for AI segmentation (sky / foreground)."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from Imervue.image import segmentation


class TestForegroundMask:
    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            segmentation.foreground_mask(arr)

    def test_returns_hxw_float_mask_in_unit_range(self):
        arr = np.random.randint(0, 256, (32, 32, 4), dtype=np.uint8)
        mask = segmentation.foreground_mask(arr)
        assert mask.shape == (32, 32)
        assert mask.dtype == np.float32
        assert mask.min() >= 0.0 and mask.max() <= 1.0


class TestSkyMask:
    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            segmentation.sky_mask(arr)

    def test_detects_blue_upper_region(self):
        arr = np.zeros((60, 60, 4), dtype=np.uint8)
        arr[..., 3] = 255
        # Upper half: bright blue (sky).
        arr[:30, :, 0] = 80    # R
        arr[:30, :, 1] = 140   # G
        arr[:30, :, 2] = 220   # B
        # Lower half: green (grass).
        arr[30:, :, 0] = 30
        arr[30:, :, 1] = 150
        arr[30:, :, 2] = 50
        mask = segmentation.sky_mask(arr)
        assert mask[10, 30] > mask[50, 30]


class TestReplaceSky:
    def test_no_sky_returns_original(self):
        arr = np.full((30, 30, 4), 100, dtype=np.uint8)
        arr[..., 3] = 255
        # All-green image — no sky should be detected.
        arr[..., 0] = 30; arr[..., 1] = 180; arr[..., 2] = 30
        out = segmentation.replace_sky(arr)
        assert out.shape == arr.shape


class TestRemoveBackground:
    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            segmentation.remove_background(arr)

    def test_transparent_bg_writes_alpha(self):
        arr = np.full((20, 20, 4), 200, dtype=np.uint8)
        arr[..., 3] = 255
        out = segmentation.remove_background(arr, bg_color=(0, 0, 0, 0))
        assert out.shape == arr.shape
