"""Tests for lossless rotation via PIL."""
import numpy as np
from PIL import Image


class TestLosslessRotate:
    """Test PIL-based lossless rotation (the core logic used by lossless_rotate.py)."""

    def test_rotate_90_dimensions(self, tmp_path):
        path = tmp_path / "test.png"
        img = Image.fromarray(np.zeros((100, 200, 3), dtype=np.uint8))
        img.save(str(path))

        loaded = Image.open(str(path))
        rotated = loaded.transpose(Image.Transpose.ROTATE_90)
        rotated.save(str(path))

        result = Image.open(str(path))
        assert result.size == (100, 200)  # width, height swapped

    def test_rotate_180_dimensions(self, tmp_path):
        path = tmp_path / "test.png"
        img = Image.fromarray(np.zeros((100, 200, 3), dtype=np.uint8))
        img.save(str(path))

        loaded = Image.open(str(path))
        rotated = loaded.transpose(Image.Transpose.ROTATE_180)
        rotated.save(str(path))

        result = Image.open(str(path))
        assert result.size == (200, 100)  # same dimensions

    def test_rotate_270_dimensions(self, tmp_path):
        path = tmp_path / "test.png"
        img = Image.fromarray(np.zeros((100, 200, 3), dtype=np.uint8))
        img.save(str(path))

        loaded = Image.open(str(path))
        rotated = loaded.transpose(Image.Transpose.ROTATE_270)
        rotated.save(str(path))

        result = Image.open(str(path))
        assert result.size == (100, 200)  # width, height swapped

    def test_rotate_preserves_content(self, tmp_path):
        """A red pixel at top-left should move after rotation."""
        path = tmp_path / "pixel.png"
        arr = np.zeros((10, 10, 3), dtype=np.uint8)
        arr[0, 0] = [255, 0, 0]
        Image.fromarray(arr).save(str(path))

        loaded = Image.open(str(path))
        rotated = loaded.transpose(Image.Transpose.ROTATE_90)
        result = np.array(rotated)
        # After 90° CCW, top-left → bottom-left
        assert result[9, 0, 0] == 255
        assert result[0, 0, 0] == 0
