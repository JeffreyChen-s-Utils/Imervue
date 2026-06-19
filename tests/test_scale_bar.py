"""Tests for the scale-bar overlay and nice-length rounding."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.scale_bar import add_scale_bar, nice_length


def _rgba(h=80, w=120, value=128):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_nice_length_rounds_to_1_2_5():
    assert nice_length(123) == 100
    assert nice_length(280) == 200
    assert nice_length(600) == 500
    assert nice_length(9) == 5
    assert nice_length(0) == 1.0


def test_scale_bar_shape_and_alpha():
    out = add_scale_bar(_rgba(), px_per_unit=4.0, unit="mm")
    assert out.shape == (80, 120, 4)
    assert np.all(out[..., 3] == 255)


def test_scale_bar_draws_white_marks():
    img = _rgba(value=0)  # black canvas
    out = add_scale_bar(img, px_per_unit=4.0)
    # The white bar introduces bright pixels into a previously black image.
    assert out[..., :3].max() > 200


def test_accepts_rgb_input():
    out = add_scale_bar(_rgba()[..., :3], px_per_unit=2.0)
    assert out.shape == (80, 120, 4)


def test_invalid_calibration_raises():
    with pytest.raises(ValueError):
        add_scale_bar(_rgba(), px_per_unit=0.0)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        add_scale_bar(np.zeros((8, 8), dtype=np.uint8), px_per_unit=4.0)


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.scale_bar_dialog import ScaleBarDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_rgba()).save(str(path))
    dialog = ScaleBarDialog(object(), str(path))
    try:
        assert dialog._unit.text() == "um"
    finally:
        dialog.deleteLater()
