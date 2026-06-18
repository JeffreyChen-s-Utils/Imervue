"""Tests for dark-channel-prior dehaze."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.dehaze import dehaze


def _hazy_rgba(h=48, w=48, airlight=210, transmission=0.55):
    """A two-tone scene pushed toward a bright airlight (low contrast)."""
    base = np.empty((h, w, 3), dtype=np.float32)
    base[:, : w // 2] = 40.0
    base[:, w // 2 :] = 90.0
    hazed = base * transmission + airlight * (1.0 - transmission)
    rgb = np.clip(hazed, 0, 255).astype(np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def _flat_rgba(value=144, h=24, w=24):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_zero_strength_is_identity():
    img = _hazy_rgba()
    assert np.array_equal(dehaze(img, 0.0), img)


def test_preserves_shape_dtype_alpha():
    img = _hazy_rgba()
    out = dehaze(img, 1.0)
    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert np.all(out[..., 3] == 255)


def test_dehaze_increases_contrast():
    img = _hazy_rgba()
    out = dehaze(img, 1.0)
    assert out[..., :3].std() > img[..., :3].std()


def test_strength_clamped_above_one():
    img = _hazy_rgba()
    assert np.array_equal(dehaze(img, 5.0), dehaze(img, 1.0))


def test_flat_image_stays_flat():
    img = _flat_rgba()
    out = dehaze(img, 1.0)
    assert out.shape == img.shape
    assert out[..., :3].std() < 1.0


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        dehaze(np.zeros((8, 8), dtype=np.uint8), 1.0)


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.local_contrast_dialog import LocalContrastDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_hazy_rgba()).save(str(path))
    dialog = LocalContrastDialog(object(), str(path))
    try:
        assert dialog._dehaze.minimum() == 0
        assert dialog._clarity.minimum() == -100
        assert dialog._texture.maximum() == 100
    finally:
        dialog.deleteLater()
