"""Tests for image_loader: load_image_file and _scan_images."""
import os
import numpy as np
import pytest
from PIL import Image

from Imervue.gpu_image_view.images.image_loader import load_image_file, _scan_images


class TestLoadImageFile:
    def test_load_png_returns_rgba(self, sample_png):
        result = load_image_file(sample_png)
        assert result.ndim == 3
        assert result.shape[2] == 4
        assert result.dtype == np.uint8

    def test_load_jpeg_returns_rgba(self, sample_jpeg):
        result = load_image_file(sample_jpeg)
        assert result.ndim == 3
        assert result.shape[2] == 4

    def test_load_grayscale_returns_rgba(self, sample_grayscale_png):
        result = load_image_file(sample_grayscale_png)
        assert result.ndim == 3
        assert result.shape[2] == 4

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(Exception):
            load_image_file(str(tmp_path / "nonexistent.png"))


class TestScanImages:
    def test_scan_finds_supported_files(self, image_folder):
        results = _scan_images(image_folder)
        basenames = [os.path.basename(p) for p in results]
        assert "alpha.png" in basenames
        assert "beta.jpg" in basenames
        assert "gamma.png" in basenames
        assert "delta.bmp" in basenames

    def test_scan_sorted_alphabetically(self, image_folder):
        results = _scan_images(image_folder)
        basenames = [os.path.basename(p).lower() for p in results]
        assert basenames == sorted(basenames)

    def test_scan_ignores_non_image(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.csv").write_text("a,b")
        (tmp_path / "real.png").write_bytes(
            Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8)).tobytes()
        )
        # Create a real png
        img = Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8))
        img.save(str(tmp_path / "real.png"))
        results = _scan_images(str(tmp_path))
        assert len(results) == 1
        assert results[0].endswith("real.png")

    def test_scan_empty_dir(self, tmp_path):
        results = _scan_images(str(tmp_path))
        assert results == []

    def test_scan_nonexistent_dir(self):
        results = _scan_images("/nonexistent/path/xyz")
        assert results == []
