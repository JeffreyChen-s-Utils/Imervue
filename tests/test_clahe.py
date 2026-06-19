"""Tests for CLAHE adaptive histogram equalization."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.clahe import apply_clahe


def _gradient_rgba(h=64, w=64):
    ramp = np.linspace(40, 210, w, dtype=np.float32)
    rgb = np.repeat(ramp[None, :], h, axis=0)[..., None].repeat(3, axis=2).astype(np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def _low_contrast_rgba(h=64, w=64):
    rng = np.random.default_rng(0)
    rgb = (120 + rng.integers(-8, 9, size=(h, w, 3))).astype(np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_shape_dtype_alpha_preserved():
    img = _gradient_rgba()
    out = apply_clahe(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert np.all(out[..., 3] == 255)


def test_increases_local_contrast():
    img = _low_contrast_rgba()
    out = apply_clahe(img, clip_limit=3.0, tiles=8)
    assert out[..., :3].std() > img[..., :3].std()


def test_single_tile_runs():
    img = _gradient_rgba(16, 16)
    out = apply_clahe(img, tiles=1)
    assert out.shape == img.shape


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        apply_clahe(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.clahe_dialog import ClaheDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_gradient_rgba(32, 32)).save(str(path))
    dialog = ClaheDialog(object(), str(path))
    try:
        assert dialog._tiles.value() == 8
    finally:
        dialog.deleteLater()
