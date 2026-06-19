"""Tests for anaglyph 3D stereo compositing."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.anaglyph import COLOR, DUBOIS, GRAY, METHODS, anaglyph


def _solid(rgb, h=16, w=16):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = rgb
    arr[..., 3] = 255
    return arr


def test_color_takes_red_from_left_cyan_from_right():
    left = _solid((255, 0, 0))    # pure red left
    right = _solid((0, 0, 255))   # pure blue right
    out = anaglyph(left, right, COLOR)[..., :3]
    assert out[0, 0, 0] == 255    # red from left
    assert out[0, 0, 2] == 255    # blue from right
    assert out[0, 0, 1] == 0      # green from right (0)


def test_shape_and_alpha():
    out = anaglyph(_solid((120, 130, 140)), _solid((40, 50, 60)), DUBOIS)
    assert out.shape == (16, 16, 4)
    assert np.all(out[..., 3] == 255)


def test_all_methods_run():
    left, right = _solid((100, 150, 200)), _solid((90, 140, 190))
    for method in METHODS:
        assert anaglyph(left, right, method).shape[2] == 4


def test_resizes_mismatched_right():
    left = _solid((200, 100, 50), 20, 30)
    right = _solid((50, 100, 200), 10, 10)
    out = anaglyph(left, right, GRAY)
    assert out.shape == (20, 30, 4)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        anaglyph(np.zeros((8, 8), dtype=np.uint8), _solid((1, 2, 3)))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.anaglyph_dialog import AnaglyphDialog

    path = tmp_path / "left.png"
    PILImage.fromarray(_solid((120, 60, 30))).save(str(path))
    dialog = AnaglyphDialog(object(), str(path))
    try:
        assert dialog._method.count() == len(METHODS)
    finally:
        dialog.deleteLater()
