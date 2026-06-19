"""Tests for scientific colour maps."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.colormap import COLORMAPS, apply_colormap


def _gray_rgba(value, h=8, w=8):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def _ramp_rgba(h=4, w=256):
    ramp = np.arange(w, dtype=np.uint8)
    rgb = np.repeat(ramp[None, :], h, axis=0)[..., None].repeat(3, axis=2)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_shape_and_alpha():
    out = apply_colormap(_gray_rgba(128), "viridis")
    assert out.shape == (8, 8, 4)
    assert np.all(out[..., 3] == 255)


def test_all_maps_supported():
    for name in COLORMAPS:
        assert apply_colormap(_gray_rgba(100), name).shape[2] == 4


def test_dark_and_bright_map_differently():
    dark = apply_colormap(_gray_rgba(0), "viridis")[0, 0, :3]
    bright = apply_colormap(_gray_rgba(255), "viridis")[0, 0, :3]
    assert not np.array_equal(dark, bright)


def test_ramp_produces_many_colors():
    out = apply_colormap(_ramp_rgba(), "jet")
    assert len({tuple(c) for c in out[0, :, :3]}) > 50


def test_unknown_map_falls_back():
    assert apply_colormap(_gray_rgba(50), "nonexistent").shape[2] == 4


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        apply_colormap(np.zeros((4, 4), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.colormap_dialog import ColormapDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_gray_rgba(120, 20, 20)).save(str(path))
    dialog = ColormapDialog(object(), str(path))
    try:
        assert dialog._combo.count() == len(COLORMAPS)
    finally:
        dialog.deleteLater()
