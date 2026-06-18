"""Tests for the AI Outpaint plugin (canvas expansion + diffusion fill)."""
from __future__ import annotations

import numpy as np
import pytest

from ai_outpaint.outpaint import expand_canvas, outpaint


def _rgb(h, w, value):
    return np.full((h, w, 3), value, dtype=np.uint8)


def test_expand_canvas_shape_and_placement():
    arr = _rgb(10, 20, 100)
    canvas, mask = expand_canvas(arr, left=2, top=3, right=4, bottom=5)
    assert canvas.shape == (10 + 3 + 5, 20 + 2 + 4, 4)
    # Original pixels land at the offset and are preserved.
    assert np.all(canvas[3:13, 2:22, :3] == 100)


def test_expand_canvas_mask_marks_only_border():
    arr = _rgb(8, 8, 50)
    _canvas, mask = expand_canvas(arr, 4, 4, 4, 4)
    assert not mask[4:12, 4:12].any()   # original region kept
    assert mask[0, 0]                   # border to fill


def test_expand_canvas_rejects_bad_shape():
    with pytest.raises(ValueError):
        expand_canvas(np.zeros((4, 4), dtype=np.uint8), 1, 1, 1, 1)


def test_outpaint_grows_and_preserves_centre():
    arr = _rgb(8, 8, 100)
    out = outpaint(arr, padding=4, iterations=60)
    assert out.shape == (16, 16, 4)
    assert np.all(out[4:12, 4:12, :3] == 100)   # original unchanged
    assert out[0:4, :, :3].mean() > 50          # border filled toward edge


def test_outpaint_zero_padding_returns_rgba():
    out = outpaint(_rgb(8, 8, 100), padding=0)
    assert out.shape == (8, 8, 4)
    assert np.all(out[..., :3] == 100)


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from ai_outpaint.ai_outpaint_plugin import OutpaintDialog
    path = tmp_path / "scene.png"
    PILImage.fromarray(_rgb(20, 20, 80)).save(str(path))
    dialog = OutpaintDialog(object(), str(path))
    try:
        assert dialog._padding.value() == 64
        assert dialog._padding.maximum() == 512
    finally:
        dialog.deleteLater()
