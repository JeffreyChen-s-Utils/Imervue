"""Tests for the photo frame / caption compositor."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.photo_frame import FrameOptions, add_frame


def _solid(value=120, h=40, w=60):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_matte_grows_by_border():
    out = add_frame(_solid(120, 40, 60), FrameOptions(border=20, color=(255, 255, 255)))
    assert out.shape == (40 + 40, 60 + 40, 4)
    # The top-left corner is matte, not the original image colour.
    assert tuple(out[0, 0, :3]) == (255, 255, 255)


def test_bottom_extra_adds_height_only():
    out = add_frame(_solid(120, 40, 60), FrameOptions(border=10, bottom_extra=30))
    assert out.shape == (40 + 20 + 30, 60 + 20, 4)


def test_caption_draws_text_in_band():
    plain = add_frame(_solid(0, 40, 60), FrameOptions(border=10, bottom_extra=40, color=(0, 0, 0)))
    captioned = add_frame(
        _solid(0, 40, 60),
        FrameOptions(border=10, bottom_extra=40, color=(0, 0, 0),
                     caption="Hello", text_color=(255, 255, 255)),
    )
    # Drawing white text into the black bottom band changes pixels.
    assert not np.array_equal(plain, captioned)


def test_default_options_run():
    out = add_frame(_solid())
    assert out.shape[2] == 4


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        add_frame(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.photo_frame_dialog import PhotoFrameDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_solid()).save(str(path))
    dialog = PhotoFrameDialog(object(), str(path))
    try:
        assert dialog._border.value() == 40
    finally:
        dialog.deleteLater()
