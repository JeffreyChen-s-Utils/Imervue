"""Tests for noise reduction and sharpening."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from Imervue.image import denoise


class TestReduceNoise:
    def test_zero_strength_passes_through(self):
        arr = np.random.randint(0, 256, (16, 16, 4), dtype=np.uint8)
        out = denoise.reduce_noise(arr, strength=0.0)
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            denoise.reduce_noise(arr, strength=0.5)

    def test_noise_reduced_on_noisy_patch(self):
        rng = np.random.default_rng(42)
        arr = np.full((64, 64, 4), 128, dtype=np.uint8)
        arr[..., 3] = 255
        noise = rng.integers(-40, 41, (64, 64, 3))
        arr[..., :3] = np.clip(arr[..., :3].astype(np.int16) + noise, 0, 255)
        out = denoise.reduce_noise(arr, strength=0.8)
        assert out[..., :3].std() < arr[..., :3].std()

    def test_luminance_only_mode(self):
        arr = np.random.randint(0, 256, (32, 32, 4), dtype=np.uint8)
        arr[..., 3] = 255
        out = denoise.reduce_noise(arr, strength=0.5, preserve_color=False)
        assert out.shape == arr.shape


class TestSharpen:
    def test_zero_amount_passes_through(self):
        arr = np.zeros((16, 16, 4), dtype=np.uint8)
        out = denoise.sharpen(arr, amount=0.0)
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            denoise.sharpen(arr, amount=1.0)

    def test_sharpen_increases_edge_contrast(self):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        arr[..., :3] = 100
        arr[:, 16:, :3] = 150   # soft step
        arr[..., 3] = 255
        out = denoise.sharpen(arr, amount=2.0, radius=1.5)
        # Compare the step magnitude on the boundary column.
        before = int(arr[10, 16, 0]) - int(arr[10, 15, 0])
        after = int(out[10, 16, 0]) - int(out[10, 15, 0])
        assert after >= before
