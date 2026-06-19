"""Tests for Otsu global auto-threshold."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.otsu import otsu_binarize, otsu_threshold


def _bimodal_rgba(h=32, w=32):
    rgb = np.full((h, w, 3), 40, dtype=np.uint8)
    rgb[:, w // 2 :] = 210   # a bright half
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_threshold_between_modes():
    luma = np.where(np.arange(32)[None, :] < 16, 40.0, 210.0).repeat(8, axis=0)
    t = otsu_threshold(luma)
    # The threshold lands on the dark mode; binarizing with `> t` still
    # separates the two classes cleanly.
    assert 40 <= t < 210


def test_binarize_splits_two_halves():
    out = otsu_binarize(_bimodal_rgba())[..., 0]
    assert out[0, 0] == 0       # dark half → black
    assert out[0, 31] == 255    # bright half → white


def test_invert_flips_result():
    normal = otsu_binarize(_bimodal_rgba())[..., 0]
    inverted = otsu_binarize(_bimodal_rgba(), invert=True)[..., 0]
    assert np.array_equal(inverted, 255 - normal)


def test_output_is_pure_bw_rgba():
    out = otsu_binarize(_bimodal_rgba())
    assert out.shape[2] == 4
    assert set(np.unique(out[..., :3]).tolist()) <= {0, 255}
    assert np.all(out[..., 3] == 255)


def test_empty_histogram_returns_mid():
    assert otsu_threshold(np.empty((0, 0))) == 128


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        otsu_binarize(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.otsu_dialog import OtsuDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_bimodal_rgba()).save(str(path))
    dialog = OtsuDialog(object(), str(path))
    try:
        assert not dialog._invert.isChecked()
    finally:
        dialog.deleteLater()
