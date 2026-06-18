"""Tests for polynomial background flattening."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.flatten_field import flatten_background


def _gradient_rgba(h=80, w=80, lo=60, hi=200):
    ramp = np.linspace(lo, hi, w, dtype=np.float32)
    rgb = np.repeat(ramp[None, :], h, axis=0)[..., None].repeat(3, axis=2)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_shape_dtype_alpha_preserved():
    img = _gradient_rgba()
    out = flatten_background(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert np.all(out[..., 3] == 255)


def test_removes_linear_gradient():
    img = _gradient_rgba()
    out = flatten_background(img, degree=1)
    # A pure linear ramp is exactly the modelled background → result is flat.
    assert out[..., :3].std() < img[..., :3].std()
    assert out[..., :3].std() < 8.0


def test_divide_mode_runs():
    img = _gradient_rgba()
    out = flatten_background(img, degree=2, divide=True)
    assert out.shape == img.shape
    assert out[..., :3].std() < img[..., :3].std()


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        flatten_background(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.flatten_field_dialog import FlattenFieldDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_gradient_rgba(40, 40)).save(str(path))
    dialog = FlattenFieldDialog(object(), str(path))
    try:
        assert dialog._degree.value() == 2
        assert not dialog._divide.isChecked()
    finally:
        dialog.deleteLater()
