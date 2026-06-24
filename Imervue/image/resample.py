"""Shared reverse-map resampling helpers (pure NumPy).

The geometric warps in the viewer (``distort``, ``polar``, ``kaleidoscope`` …)
are all reverse maps: build the output coordinate grid, compute where each
output pixel samples the source, then resample. The alpha-promotion and bilinear
gather are identical across them, so they live here instead of being copied.
"""
from __future__ import annotations

import numpy as np

RGB_CHANNELS = 3
RGBA_CHANNELS = 4
OPAQUE = 255
_MAX_8BIT = 255


def ensure_rgba(arr: np.ndarray) -> np.ndarray:
    """Return *arr* as ``HxWx4``, appending an opaque alpha channel if needed."""
    if arr.shape[2] == RGBA_CHANNELS:
        return arr
    alpha = np.full((*arr.shape[:2], 1), OPAQUE, dtype=np.uint8)
    return np.concatenate([arr, alpha], axis=2)


def sample_bilinear(rgba: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> np.ndarray:
    """Bilinearly sample *rgba* at fractional coordinates *sx*, *sy*.

    Coordinates are clamped to the image bounds (edge extension), so callers can
    pass any reverse-mapped grid without masking out-of-range samples.
    """
    h, w = rgba.shape[:2]
    sx = np.clip(sx, 0, w - 1)
    sy = np.clip(sy, 0, h - 1)
    x0 = np.floor(sx).astype(np.int64)
    y0 = np.floor(sy).astype(np.int64)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    fx = (sx - x0)[..., None]
    fy = (sy - y0)[..., None]
    top = rgba[y0, x0] * (1 - fx) + rgba[y0, x1] * fx
    bottom = rgba[y1, x0] * (1 - fx) + rgba[y1, x1] * fx
    return np.clip(np.rint(top * (1 - fy) + bottom * fy), 0, _MAX_8BIT).astype(np.uint8)
