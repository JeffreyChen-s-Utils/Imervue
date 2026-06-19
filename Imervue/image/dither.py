"""Ordered (Bayer) dithering.

Quantizes each channel to a few levels while scattering the quantization error
through a tiled Bayer threshold matrix, giving the deterministic, tileable
retro / newspaper-print look. Distinct from the paint module's halftone (which
draws variable-radius dots); this is a per-pixel level reduction.

Pure NumPy and fully vectorised — no serial error-diffusion loop.
"""
from __future__ import annotations

import numpy as np

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_MAX_LEVEL = 255.0
_MIN_LEVELS = 2
_MAX_LEVELS = 8
DEFAULT_LEVELS = 2

# 4x4 Bayer matrix normalised to (0, 1).
_BAYER4 = np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
], dtype=np.float32) / 16.0


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def ordered_dither(arr: np.ndarray, levels: int = DEFAULT_LEVELS) -> np.ndarray:
    """Return *arr* ordered-dithered to *levels* per channel; HxWx4 RGBA."""
    _validate(arr)
    levels = int(np.clip(levels, _MIN_LEVELS, _MAX_LEVELS))
    h, w = arr.shape[:2]
    rgb = arr[..., :3].astype(np.float32)
    step = _MAX_LEVEL / (levels - 1)

    tile = _BAYER4.shape[0]
    threshold = np.tile(_BAYER4, (-(-h // tile), -(-w // tile)))[:h, :w]
    biased = rgb + ((threshold[..., None] - 0.5) * step)
    quantized = np.clip(np.round(biased / step), 0, levels - 1) * step

    out = np.empty((h, w, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = np.clip(np.rint(quantized), 0, 255).astype(np.uint8)
    out[..., 3] = arr[..., 3] if arr.shape[2] == _RGBA_CHANNELS else _OPAQUE
    return out
