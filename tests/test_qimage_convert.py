"""Tests for the PIL <-> QImage converters."""
from __future__ import annotations

import numpy as np
from PIL import Image
from PySide6.QtGui import QImage

from Imervue.system.qimage_convert import pil_to_qimage, qimage_to_pil


def _pil_to_qimage(img: Image.Image) -> QImage:
    # Independent reference conversion, so the round trip is not checked
    # against the function under test.
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    q = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return q.copy()


class TestQImagePilConversion:
    def test_round_trip_preserves_pixels(self, qapp):
        arr = np.zeros((20, 30, 4), dtype=np.uint8)
        arr[..., 0] = 200  # red
        arr[..., 3] = 255
        original = Image.fromarray(arr, "RGBA")
        q = _pil_to_qimage(original)
        restored = qimage_to_pil(q)
        assert restored.size == original.size
        assert restored.mode == "RGBA"
        assert np.array_equal(np.array(restored), arr)

    def test_handles_solid_color(self, qapp):
        arr = np.full((10, 10, 4), 128, dtype=np.uint8)
        arr[..., 3] = 255
        q = _pil_to_qimage(Image.fromarray(arr, "RGBA"))
        restored = qimage_to_pil(q)
        assert (np.array(restored)[..., 0] == 128).all()


class TestPilToQImage:
    def test_rgb_is_promoted_to_rgba(self, qapp):
        q = pil_to_qimage(Image.new("RGB", (3, 2), (10, 20, 30)))
        assert q.format() == QImage.Format.Format_RGBA8888
        assert (q.width(), q.height()) == (3, 2)
        assert q.pixelColor(1, 1).getRgb() == (10, 20, 30, 255)

    def test_owns_its_buffer(self, qapp):
        img = Image.new("RGBA", (4, 4), (1, 2, 3, 4))
        q = pil_to_qimage(img)
        del img
        assert q.pixelColor(0, 0).getRgb() == (1, 2, 3, 4)

    def test_round_trip_through_both_converters(self, qapp):
        arr = np.random.default_rng(3).integers(0, 256, (5, 7, 4), dtype=np.uint8)
        back = qimage_to_pil(pil_to_qimage(Image.fromarray(arr, "RGBA")))
        assert np.array_equal(np.array(back), arr)

    def test_grayscale_is_converted(self, qapp):
        q = pil_to_qimage(Image.new("L", (2, 2), 128))
        assert q.pixelColor(0, 0).getRgb() == (128, 128, 128, 255)
