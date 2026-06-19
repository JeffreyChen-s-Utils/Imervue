"""Tests for Sauvola document binarization."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.binarize import sauvola_binarize


def _page_rgba(h=48, w=48):
    """A light page with darker 'text' blocks and a shading gradient."""
    page = np.linspace(170, 230, w, dtype=np.float32)[None, :].repeat(h, axis=0)
    page[10:20, 10:30] = 40   # a dark text block
    rgb = np.clip(page, 0, 255).astype(np.uint8)[..., None].repeat(3, axis=2)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_output_is_pure_black_or_white():
    out = sauvola_binarize(_page_rgba())
    values = np.unique(out[..., :3])
    assert set(values.tolist()) <= {0, 255}
    assert np.all(out[..., 3] == 255)


def test_dark_text_becomes_black_light_page_white():
    out = sauvola_binarize(_page_rgba())[..., 0]
    assert out[15, 20] == 0      # inside the dark text block
    assert out[5, 45] == 255     # bright page corner


def test_shape_preserved():
    img = _page_rgba()
    assert sauvola_binarize(img).shape == (48, 48, 4)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        sauvola_binarize(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.binarize_dialog import BinarizeDialog

    path = tmp_path / "page.png"
    PILImage.fromarray(_page_rgba()).save(str(path))
    dialog = BinarizeDialog(object(), str(path))
    try:
        assert dialog._window.value() == 25
    finally:
        dialog.deleteLater()
