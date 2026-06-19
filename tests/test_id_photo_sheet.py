"""Tests for the passport / ID photo sheet imposition."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.id_photo_sheet import PAPER_SIZES_IN, id_photo_sheet


def _face(value=150, h=120, w=100):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_sheet_matches_paper_pixels():
    out = id_photo_sheet(_face(), paper="4x6", dpi=300)
    assert out.shape == (round(6.0 * 300), round(4.0 * 300), 4)
    assert np.all(out[..., 3] == 255)


def test_tiles_multiple_copies():
    # On 4x6 at 300 DPI, 35x45 mm photos tile into several copies.
    out = id_photo_sheet(_face(), photo_mm=(35.0, 45.0), paper="4x6", dpi=300)
    # The grey face content appears (not a blank white sheet).
    grey = np.count_nonzero(np.all(np.abs(out[..., :3].astype(int) - 150) < 5, axis=-1))
    assert grey > 0


def test_all_papers_supported():
    for paper in PAPER_SIZES_IN:
        out = id_photo_sheet(_face(40, 40), paper=paper, dpi=72)
        assert out.shape[2] == 4


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        id_photo_sheet(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.id_photo_sheet_dialog import IdPhotoSheetDialog

    path = tmp_path / "face.png"
    PILImage.fromarray(_face()).save(str(path))
    dialog = IdPhotoSheetDialog(object(), str(path))
    try:
        assert dialog._size_combo.count() == 4
        assert dialog._paper_combo.count() == len(PAPER_SIZES_IN)
    finally:
        dialog.deleteLater()
