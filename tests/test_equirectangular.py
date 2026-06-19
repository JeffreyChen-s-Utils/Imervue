"""Tests for the 360° tiny-planet reprojection."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.equirectangular import is_equirectangular, tiny_planet


def _pano_rgba(h=64, w=128):
    """Top half blue (sky), bottom half red (ground) — a 2:1 panorama."""
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[: h // 2] = (0, 0, 255)
    rgb[h // 2 :] = (255, 0, 0)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_is_equirectangular_detects_2to1():
    assert is_equirectangular(_pano_rgba(64, 128))
    assert not is_equirectangular(_pano_rgba(64, 64))


def test_tiny_planet_output_shape_and_alpha():
    out = tiny_planet(_pano_rgba(), size=200)
    assert out.shape == (200, 200, 4)
    assert np.all(out[..., 3] == 255)


def test_ground_curls_to_centre():
    out = tiny_planet(_pano_rgba(), size=200)
    centre = out[100, 100, :3]
    corner = out[0, 0, :3]
    # Centre samples the nadir (red ground); corners sample the sky (blue).
    assert centre[0] > centre[2]
    assert corner[2] > corner[0]


def test_accepts_rgb_input():
    rgb = _pano_rgba()[..., :3]
    out = tiny_planet(rgb, size=64)
    assert out.shape == (64, 64, 4)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        tiny_planet(np.zeros((4, 4), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.tiny_planet_dialog import TinyPlanetDialog

    path = tmp_path / "pano.png"
    PILImage.fromarray(_pano_rgba()).save(str(path))
    dialog = TinyPlanetDialog(object(), str(path))
    try:
        assert dialog._size.minimum() == 512
        assert dialog._size.maximum() == 2048
    finally:
        dialog.deleteLater()
