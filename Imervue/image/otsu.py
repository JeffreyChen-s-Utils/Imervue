"""Otsu global auto-threshold.

Picks the single luminance threshold that best separates an image into two
classes by maximising between-class variance — the standard parameter-free
binarization. Complements the adaptive Sauvola binarizer: Otsu is global and
needs no window, ideal for evenly-lit scans, masks and silhouettes.

Pure NumPy: a fully-vectorised sweep over the 256-bin histogram.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.sharpness import to_luma

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_LEVELS = 256


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def otsu_threshold(luma: np.ndarray) -> int:
    """Return the Otsu threshold (0-255) for a 2-D luma plane."""
    hist = np.bincount(
        np.clip(np.rint(luma), 0, 255).astype(np.int64).ravel(), minlength=_LEVELS,
    ).astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return _LEVELS // 2
    levels = np.arange(_LEVELS, dtype=np.float64)
    weight_bg = np.cumsum(hist)
    weight_fg = total - weight_bg
    cum_mean = np.cumsum(hist * levels)
    grand_mean = cum_mean[-1]
    valid = (weight_bg > 0) & (weight_fg > 0)
    mean_bg = np.divide(cum_mean, weight_bg, out=np.zeros_like(cum_mean), where=weight_bg > 0)
    mean_fg = np.divide(grand_mean - cum_mean, weight_fg,
                        out=np.zeros_like(cum_mean), where=weight_fg > 0)
    between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
    between[~valid] = -1.0
    return int(np.argmax(between))


def otsu_binarize(arr: np.ndarray, *, invert: bool = False) -> np.ndarray:
    """Binarize *arr* (HxWx3/4 uint8) at its Otsu threshold; returns RGBA."""
    _validate(arr)
    luma = to_luma(arr)
    threshold = otsu_threshold(luma)
    foreground = luma <= threshold if invert else luma > threshold
    binary = np.where(foreground, _OPAQUE, 0).astype(np.uint8)
    out = np.empty((*luma.shape, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = binary[..., None]
    out[..., 3] = _OPAQUE
    return out
