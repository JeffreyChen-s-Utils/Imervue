"""Tests for the pixel-sort glitch effect."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.pixel_sort import pixel_sort


def _noise_rgba(h=24, w=24, seed=0):
    rng = np.random.default_rng(seed)
    rgb = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def _luma(rgb):
    return rgb[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def test_shape_and_alpha_preserved():
    out = pixel_sort(_noise_rgba())
    assert out.shape == (24, 24, 4)
    assert np.all(out[..., 3] == 255)


def test_full_band_sorts_each_row_ascending():
    img = _noise_rgba()
    out = pixel_sort(img, 0, 255)
    brightness = _luma(out)
    # With the whole range in-band, every row is sorted by brightness.
    assert np.all(np.diff(brightness, axis=1) >= -1e-3)


def test_preserves_pixel_multiset_per_row():
    img = _noise_rgba()
    out = pixel_sort(img, 0, 255)
    before = np.sort(_luma(img), axis=1)
    after = np.sort(_luma(out), axis=1)
    assert np.allclose(before, after)


def test_vertical_sorts_columns():
    img = _noise_rgba()
    out = pixel_sort(img, 0, 255, vertical=True)
    brightness = _luma(out)
    assert np.all(np.diff(brightness, axis=0) >= -1e-3)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        pixel_sort(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.pixel_sort_dialog import PixelSortDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_noise_rgba()).save(str(path))
    dialog = PixelSortDialog(object(), str(path))
    try:
        assert dialog._lower.value() == 60
        assert dialog._upper.value() == 200
    finally:
        dialog.deleteLater()
