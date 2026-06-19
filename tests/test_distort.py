"""Tests for geometric distortion filters."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.distort import MODES, PINCH, RIPPLE, SWIRL, distort


def _checker_rgba(h=40, w=40):
    yy, xx = np.mgrid[0:h, 0:w]
    rgb = np.where(((xx // 5 + yy // 5) % 2)[..., None] == 0, 220, 40).astype(np.uint8)
    rgb = np.repeat(rgb, 3, axis=2)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_shape_and_alpha_preserved():
    out = distort(_checker_rgba(), SWIRL, 0.5)
    assert out.shape == (40, 40, 4)
    assert np.all(out[..., 3] == 255)


def test_zero_strength_is_identity_for_all_modes():
    img = _checker_rgba()
    for mode in MODES:
        out = distort(img, mode, 0.0)
        assert np.array_equal(out[..., :3], img[..., :3])


def test_swirl_changes_image():
    img = _checker_rgba()
    assert not np.array_equal(distort(img, SWIRL, 1.0), img)


def test_pinch_and_ripple_change_image():
    img = _checker_rgba()
    assert not np.array_equal(distort(img, PINCH, 0.8), img)
    assert not np.array_equal(distort(img, RIPPLE, 0.8), img)


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        distort(_checker_rgba(), "warpzone", 0.5)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        distort(np.zeros((8, 8), dtype=np.uint8), SWIRL, 0.5)


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.distort_dialog import DistortDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_checker_rgba()).save(str(path))
    dialog = DistortDialog(object(), str(path))
    try:
        assert dialog._mode.count() == len(MODES)
    finally:
        dialog.deleteLater()
