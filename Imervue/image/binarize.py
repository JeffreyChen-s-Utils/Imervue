"""Adaptive document binarization (Sauvola).

Turns an unevenly-lit photo or scan of a page into clean black-on-white, which
is both more legible and a far better input for OCR than a global threshold.
Sauvola sets a *local* threshold ``T = m·(1 + k·(s/R − 1))`` from the mean ``m``
and standard deviation ``s`` of each pixel's neighbourhood, so it tolerates
shadows and gradients that defeat a single global cutoff.

Pure NumPy: the local mean / variance are computed with the shared separable
Gaussian window from :mod:`Imervue.image.local_contrast`.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.local_contrast import blur_plane

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_DYNAMIC_RANGE = 128.0
DEFAULT_WINDOW = 25
DEFAULT_K = 0.2


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def sauvola_binarize(
    arr: np.ndarray, window: int = DEFAULT_WINDOW, k: float = DEFAULT_K,
) -> np.ndarray:
    """Return *arr* (HxWx3/4 uint8) binarized to black/white via Sauvola."""
    _validate(arr)
    radius = max(1, int(window) // 2)
    rgb = arr[..., :3].astype(np.float32)
    lum = rgb @ _LUMA_WEIGHTS
    mean = blur_plane(lum, radius)
    mean_sq = blur_plane(lum * lum, radius)
    std = np.sqrt(np.clip(mean_sq - mean * mean, 0.0, None))
    threshold = mean * (1.0 + k * (std / _DYNAMIC_RANGE - 1.0))
    binary = np.where(lum > threshold, _OPAQUE, 0).astype(np.uint8)

    out = np.empty((*lum.shape, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = binary[..., None]
    out[..., 3] = _OPAQUE
    return out
