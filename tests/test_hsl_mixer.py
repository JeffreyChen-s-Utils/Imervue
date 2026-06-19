"""Tests for the per-band HSL / colour mixer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.hsl_mixer import apply_hsl


def _solid_rgba(rgb, h=8, w=8):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = rgb
    arr[..., 3] = 255
    return arr


def test_empty_adjustments_identity():
    img = _solid_rgba((200, 50, 50))
    assert np.array_equal(apply_hsl(img, {}), img)


def test_all_zero_adjustments_identity():
    img = _solid_rgba((200, 50, 50))
    assert np.array_equal(apply_hsl(img, {"red": (0.0, 0.0, 0.0)}), img)


def test_desaturating_red_makes_it_grey():
    img = _solid_rgba((255, 0, 0))
    out = apply_hsl(img, {"red": (0.0, -1.0, 0.0)})[..., :3]
    assert abs(int(out[0, 0, 0]) - int(out[0, 0, 1])) <= 2
    assert abs(int(out[0, 0, 1]) - int(out[0, 0, 2])) <= 2


def test_dropping_red_luminance_darkens():
    img = _solid_rgba((255, 0, 0))
    out = apply_hsl(img, {"red": (0.0, 0.0, -1.0)})
    assert out[..., :3].sum() < img[..., :3].sum()


def test_red_hue_shift_moves_toward_orange():
    img = _solid_rgba((255, 0, 0))
    out = apply_hsl(img, {"red": (1.0, 0.0, 0.0)})
    # Shifting red's hue up adds green (toward orange/yellow).
    assert out[0, 0, 1] > img[0, 0, 1]


def test_far_band_leaves_pixel_unchanged_round_trip():
    # Adjusting RED must not disturb a GREEN image, and the RGB->HSV->RGB
    # round trip must preserve it within rounding.
    img = _solid_rgba((0, 200, 0))
    out = apply_hsl(img, {"red": (1.0, -1.0, 1.0)})
    assert np.all(np.abs(out[..., :3].astype(int) - img[..., :3].astype(int)) <= 2)


def test_preserves_shape_dtype_alpha():
    img = _solid_rgba((120, 80, 40))
    out = apply_hsl(img, {"orange": (0.2, 0.3, -0.2)})
    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert np.all(out[..., 3] == 255)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        apply_hsl(np.zeros((4, 4), dtype=np.uint8), {"red": (1.0, 0.0, 0.0)})


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.hsl_mixer_dialog import HslMixerDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_solid_rgba((180, 90, 60), 20, 20)).save(str(path))
    dialog = HslMixerDialog(object(), str(path))
    try:
        assert dialog._band_combo.count() == 8
        assert len(dialog._sliders) == 3
    finally:
        dialog.deleteLater()
