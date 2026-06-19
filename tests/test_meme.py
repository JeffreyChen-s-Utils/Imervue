"""Tests for the meme caption generator."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import ImageDraw, ImageFont

from Imervue.image.meme import make_meme, wrap_text


def _black_rgba(h=200, w=300):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 3] = 255
    return arr


def test_wrap_text_splits_long_lines():
    from PIL import Image
    draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    font = ImageFont.load_default()
    lines = wrap_text(draw, "the quick brown fox jumps", font, max_width=40)
    assert len(lines) > 1
    assert " ".join(lines).split() == ["the", "quick", "brown", "fox", "jumps"]


def test_wrap_text_empty():
    from PIL import Image
    draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    assert wrap_text(draw, "", ImageFont.load_default(), 100) == [""]


def test_top_text_adds_bright_pixels_at_top():
    img = _black_rgba()
    out = make_meme(img, top_text="HELLO")
    assert out.shape == (200, 300, 4)
    # White meme text appears in the top third of a previously black image.
    assert out[: 200 // 3, :, :3].max() > 200


def test_empty_text_unchanged():
    img = _black_rgba()
    assert np.array_equal(make_meme(img, "", ""), img)


def test_alpha_preserved():
    out = make_meme(_black_rgba(), bottom_text="WORLD")
    assert np.all(out[..., 3] == 255)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        make_meme(np.zeros((8, 8), dtype=np.uint8), "hi")


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.meme_dialog import MemeDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_black_rgba(64, 64)).save(str(path))
    dialog = MemeDialog(object(), str(path))
    try:
        assert dialog._top.text() == ""
    finally:
        dialog.deleteLater()
