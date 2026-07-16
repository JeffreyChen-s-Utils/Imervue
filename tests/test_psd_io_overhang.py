"""_assemble_layer_image must handle a layer overhanging the canvas.

A PSD layer can legally extend past the canvas (top<0 / left<0 / bottom>h /
right>w). The old code sliced the destination but not the source, so the
raw-bounds source mismatched the clamped destination and raised ValueError.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.psd_io import _assemble_layer_image


def _full(value: int) -> dict:
    band = np.full((4, 4), value, dtype=np.uint8)
    return {0: band.copy(), 1: band.copy(), 2: band.copy(),
            -1: np.full((4, 4), 255, dtype=np.uint8)}


def test_overhanging_layer_is_clipped_not_crashed():
    # A 4x4 layer at (-2, -2) on a 4x4 canvas: only its bottom-right 2x2 lands.
    img = _assemble_layer_image(
        _full(100), h=4, w=4, top=-2, left=-2, bottom=2, right=2)
    assert img.shape == (4, 4, 4)
    assert img[0, 0, 0] == 100      # on-canvas corner got the layer
    assert img[3, 3, 0] == 0        # outside the pasted 2x2


def test_fully_off_canvas_layer_is_blank():
    img = _assemble_layer_image(
        {0: np.full((2, 2), 100, dtype=np.uint8)},
        h=4, w=4, top=10, left=10, bottom=12, right=12)
    assert img.shape == (4, 4, 4)
    assert not img.any()


def test_on_canvas_layer_unaffected():
    img = _assemble_layer_image(
        _full(80), h=4, w=4, top=0, left=0, bottom=4, right=4)
    assert np.all(img[..., 0] == 80)
    assert np.all(img[..., 3] == 255)
