"""Tests for the photo-collage grid compositor."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.collage import build_collage


def _solid(value, h=50, w=50):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_grid_dimensions():
    imgs = [_solid(v) for v in (10, 50, 90)]
    out = build_collage(imgs, columns=2, cell=(40, 40), gap=10, margin=20)
    # 3 images / 2 cols → 2 rows.
    assert out.shape == (20 * 2 + 2 * 40 + 10, 20 * 2 + 2 * 40 + 10, 4)
    assert np.all(out[..., 3] == 255)


def test_cells_contain_image_content():
    out = build_collage([_solid(200)], columns=1, cell=(40, 40), gap=0,
                        margin=10, background=(0, 0, 0))
    # The pasted bright image leaves non-black pixels on the black canvas.
    assert out[..., :3].max() > 100


def test_single_column_stacks_rows():
    out = build_collage([_solid(10), _solid(20)], columns=1, cell=(30, 30),
                        gap=5, margin=5)
    assert out.shape[0] == 5 * 2 + 2 * 30 + 5  # two rows


def test_empty_raises():
    with pytest.raises(ValueError):
        build_collage([], columns=2)


def test_bad_image_shape_raises():
    with pytest.raises(ValueError):
        build_collage([np.zeros((8, 8), dtype=np.uint8)], columns=1)


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.collage_dialog import CollageDialog

    paths = []
    for i in range(3):
        p = tmp_path / f"img{i}.png"
        PILImage.fromarray(_solid(40 * i + 20)).save(str(p))
        paths.append(str(p))
    dialog = CollageDialog(object(), paths)
    try:
        assert dialog._columns.value() == 3
    finally:
        dialog.deleteLater()
