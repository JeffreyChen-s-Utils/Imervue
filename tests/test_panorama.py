"""Tests for the panorama stitcher wrapper."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("cv2")

from Imervue.image import panorama as pano


class TestStitchValidation:
    def test_rejects_single_image(self, tmp_path):
        p = tmp_path / "a.png"
        Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8)).save(p)
        with pytest.raises(ValueError):
            pano.stitch_panorama([str(p)])

    def test_rejects_empty_list(self):
        with pytest.raises(ValueError):
            pano.stitch_panorama([])


class TestCropBlack:
    def test_crop_all_black_is_noop(self):
        bgr = np.zeros((8, 8, 3), dtype=np.uint8)
        out = pano._crop_black(bgr)
        assert out.shape == bgr.shape

    def test_crop_trims_black_border(self):
        bgr = np.zeros((10, 10, 3), dtype=np.uint8)
        bgr[3:7, 4:8] = 128
        out = pano._crop_black(bgr)
        assert out.shape == (4, 4, 3)

    def test_crop_keeps_full_image_when_no_border(self):
        bgr = np.full((8, 8, 3), 50, dtype=np.uint8)
        out = pano._crop_black(bgr)
        assert out.shape == bgr.shape


class TestStitchFailsCleanly:
    def test_noise_images_raise_runtime_error(self, tmp_path):
        # Random noise can't be stitched — the OpenCV stitcher should return
        # a non-OK status and we should translate it to RuntimeError.
        rng = np.random.default_rng(42)
        paths = []
        for i in range(2):
            arr = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
            p = tmp_path / f"noise_{i}.png"
            Image.fromarray(arr).save(p)
            paths.append(str(p))
        with pytest.raises(RuntimeError):
            pano.stitch_panorama(paths)
