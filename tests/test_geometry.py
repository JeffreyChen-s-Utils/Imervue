"""Tests for crop, straighten, and perspective correction."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from Imervue.image import geometry


class TestCropRect:
    def test_to_pixels_clamps(self):
        rect = geometry.CropRect(x=-0.1, y=0.0, w=2.0, h=0.5)
        px, py, pw, ph = rect.to_pixels(100, 100)
        assert px == 0 and py == 0
        assert px + pw <= 100 and py + ph <= 100

    def test_apply_crop_reduces_size(self):
        arr = np.zeros((100, 100, 4), dtype=np.uint8)
        rect = geometry.CropRect(x=0.1, y=0.1, w=0.5, h=0.5)
        out = geometry.apply_crop(arr, rect)
        assert out.shape[0] == 50 and out.shape[1] == 50


class TestStraighten:
    def test_zero_angle_passes_through(self):
        arr = np.zeros((40, 40, 4), dtype=np.uint8)
        out = geometry.straighten(arr, 0.0)
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((40, 40, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            geometry.straighten(arr, 2.0)

    def test_rotation_returns_different_shape(self):
        arr = np.zeros((60, 40, 4), dtype=np.uint8)
        arr[..., 3] = 255
        out = geometry.straighten(arr, 5.0, crop_to_content=True)
        # Cropped-to-content should be smaller than the bounding rotation.
        assert out.shape[0] <= 60 and out.shape[1] <= 40
        assert out.shape[0] >= 4 and out.shape[1] >= 4


class TestCorrectPerspective:
    def test_requires_four_points(self):
        arr = np.zeros((40, 40, 4), dtype=np.uint8)
        with pytest.raises(ValueError):
            geometry.correct_perspective(arr, [(0, 0), (1, 0), (1, 1)])

    def test_identity_quad_produces_similar_image(self):
        arr = np.full((40, 40, 4), 128, dtype=np.uint8)
        arr[..., 3] = 255
        pts = [(0.0, 0.0), (39.0, 0.0), (39.0, 39.0), (0.0, 39.0)]
        out = geometry.correct_perspective(arr, pts, (40, 40))
        assert out.shape == (40, 40, 4)
        # Same source-to-destination mapping — pixels should be close.
        assert int(abs(out[20, 20, 0]) - 128) < 5

    def test_rejects_non_rgba(self):
        arr = np.zeros((40, 40, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            geometry.correct_perspective(
                arr, [(0, 0), (1, 0), (1, 1), (0, 1)],
            )
