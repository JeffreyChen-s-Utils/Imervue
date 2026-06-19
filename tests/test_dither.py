"""Tests for ordered (Bayer) dithering."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.dither import ordered_dither


def _gradient_rgba(h=32, w=32):
    ramp = np.linspace(0, 255, w, dtype=np.uint8)
    rgb = np.repeat(ramp[None, :], h, axis=0)[..., None].repeat(3, axis=2)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_two_levels_are_pure_black_white():
    out = ordered_dither(_gradient_rgba(), levels=2)
    assert set(np.unique(out[..., :3]).tolist()) <= {0, 255}
    assert np.all(out[..., 3] == 255)


def test_shape_and_alpha_preserved():
    img = _gradient_rgba()
    out = ordered_dither(img, levels=4)
    assert out.shape == img.shape
    assert out.dtype == np.uint8


def test_more_levels_keep_more_tones():
    two = np.unique(ordered_dither(_gradient_rgba(), levels=2)[..., :3]).size
    four = np.unique(ordered_dither(_gradient_rgba(), levels=4)[..., :3]).size
    assert four > two


def test_levels_clamped():
    # Out-of-range levels must not raise.
    assert ordered_dither(_gradient_rgba(), levels=99).shape[2] == 4


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        ordered_dither(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.dither_dialog import DitherDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_gradient_rgba()).save(str(path))
    dialog = DitherDialog(object(), str(path))
    try:
        assert dialog._levels.value() == 2
    finally:
        dialog.deleteLater()
