"""Tests for model-free diffusion inpainting (pure numpy, no Qt/model)."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.inpaint import inpaint_diffusion


def _solid(value, *, size=7, channels=4):
    img = np.zeros((size, size, channels), dtype=np.uint8)
    img[..., :3] = value
    if channels == 4:
        img[..., 3] = 255
    return img


class TestInpaintDiffusion:
    def test_empty_mask_returns_unchanged_copy(self):
        img = _solid((10, 20, 30))
        mask = np.zeros(img.shape[:2], dtype=bool)
        out = inpaint_diffusion(img, mask)
        assert np.array_equal(out, img)
        assert out is not img

    def test_hole_in_solid_colour_fills_with_that_colour(self):
        img = _solid((255, 0, 0))
        mask = np.zeros(img.shape[:2], dtype=bool)
        mask[2:5, 2:5] = True  # 3x3 hole, all boundary pixels are red
        out = inpaint_diffusion(img, mask)
        assert tuple(out[3, 3]) == (255, 0, 0, 255)

    def test_known_pixels_are_untouched(self):
        img = _solid((100, 100, 100))
        img[0, 0, :3] = (5, 6, 7)  # a distinctive known pixel
        mask = np.zeros(img.shape[:2], dtype=bool)
        mask[3, 3] = True
        out = inpaint_diffusion(img, mask)
        assert np.array_equal(out[~mask], img[~mask])

    def test_linear_gradient_column_is_interpolated(self):
        # Columns 0..6 hold 0,40,80,120,160,200,240; mask column 3 (value 120).
        img = np.zeros((5, 7, 4), dtype=np.uint8)
        for col in range(7):
            img[:, col, :3] = col * 40
        img[..., 3] = 255
        mask = np.zeros(img.shape[:2], dtype=bool)
        mask[:, 3] = True
        out = inpaint_diffusion(img, mask)
        # Harmonic fill of a linear gradient is the same linear value (~120).
        assert np.allclose(out[:, 3, 0], 120, atol=2)

    def test_rgb_three_channel_image(self):
        img = _solid((50, 60, 70), channels=3)
        mask = np.zeros(img.shape[:2], dtype=bool)
        mask[3, 3] = True
        out = inpaint_diffusion(img, mask)
        assert out.shape == img.shape
        assert tuple(out[3, 3]) == (50, 60, 70)

    def test_full_mask_does_not_crash(self):
        img = _solid((123, 45, 67), size=5)
        mask = np.ones(img.shape[:2], dtype=bool)
        out = inpaint_diffusion(img, mask, iterations=10)
        assert out.shape == img.shape

    def test_invalid_image_raises(self):
        with pytest.raises(ValueError, match="HxWxC uint8"):
            inpaint_diffusion(np.zeros((4, 4), dtype=np.uint8),
                              np.zeros((4, 4), dtype=bool))

    def test_mask_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="must match image"):
            inpaint_diffusion(_solid((1, 2, 3)), np.zeros((3, 3), dtype=bool))
