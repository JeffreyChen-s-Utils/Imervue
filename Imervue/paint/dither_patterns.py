"""Ordered (Bayer) dithering for low-bit-depth quantisation.

``halftone.py`` screens an image into dots; this does the complementary job of
*ordered dithering* — quantising each channel to a few levels while a tiled
Bayer threshold matrix breaks up the banding, giving the classic retro / GIF
look without the clumping of error diffusion. Pure NumPy on ``HxWx4`` uint8
RGBA (alpha preserved); the threshold matrix is also exposed for reuse.

Bayer recurrence: https://en.wikipedia.org/wiki/Ordered_dithering
"""
from __future__ import annotations

import numpy as np

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX = 255
_MIN_LEVELS = 2
# Base 2x2 Bayer index matrix; the recurrence quadrant offsets are (0, 2, 3, 1).
_BASE = np.array([[0.0, 2.0], [3.0, 1.0]])
_OFF_TL, _OFF_TR, _OFF_BL, _OFF_BR = 0.0, 2.0, 3.0, 1.0
_QUAD = 4.0


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != _RGBA_CHANNELS or arr.dtype != np.uint8:
        raise ValueError(f"expected HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}")


def bayer_matrix(order: int) -> np.ndarray:
    """Return the ``2**order`` square Bayer threshold matrix, values in ``[0, 1)``.

    ``order`` must be >= 1 (order 1 is the 2x2 base matrix). Every cell holds a
    distinct threshold, evenly spread across ``[0, 1)``.
    """
    if order < 1:
        raise ValueError(f"order must be >= 1, got {order}")
    matrix = _BASE.copy()
    for _ in range(order - 1):
        matrix = np.block([
            [_QUAD * matrix + _OFF_TL, _QUAD * matrix + _OFF_TR],
            [_QUAD * matrix + _OFF_BL, _QUAD * matrix + _OFF_BR],
        ])
    size = matrix.shape[0]
    return matrix / (size * size)


def threshold_map(height: int, width: int, order: int = 2) -> np.ndarray:
    """Return an ``height x width`` float threshold map tiling :func:`bayer_matrix`."""
    matrix = bayer_matrix(order)
    size = matrix.shape[0]
    reps = (height // size + 1, width // size + 1)
    return np.tile(matrix, reps)[:height, :width]


def apply_ordered_dither(
    image: np.ndarray, levels: int = 2, *, order: int = 2,
) -> np.ndarray:
    """Quantise *image* to *levels* per channel using ordered (Bayer) dithering.

    ``levels`` (>= 2) is the number of output steps per channel; ``order`` sizes
    the Bayer matrix. Alpha is preserved. Raises ``ValueError`` for an invalid
    image or fewer than two levels.
    """
    _validate(image)
    if levels < _MIN_LEVELS:
        raise ValueError(f"levels must be >= {_MIN_LEVELS}, got {levels}")
    height, width = image.shape[:2]
    thresholds = threshold_map(height, width, order)[..., np.newaxis]
    normalized = image[..., :_RGB_CHANNELS].astype(np.float64) / _MAX
    span = levels - 1
    # floor(v * span + t) keeps the extremes exact (white stays white, black
    # stays black) and only dithers the levels in between.
    index = np.clip(np.floor(normalized * span + thresholds), 0, span)
    quantized = index / span
    out = image.copy()
    out[..., :_RGB_CHANNELS] = np.clip(
        np.rint(quantized * _MAX), 0, _MAX).astype(np.uint8)
    return out
