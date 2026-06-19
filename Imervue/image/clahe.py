"""CLAHE — Contrast-Limited Adaptive Histogram Equalization.

Boosts *local* contrast by equalizing the histogram of small tiles rather than
the whole frame, with a clip limit that caps noise amplification in flat areas.
The classic enhancer for hazy, foggy, low-contrast, microscopy and forensic
images, complementing the global tone-curve / clarity tools.

Pure NumPy: per-tile clipped-histogram CDF lookup tables, bilinearly
interpolated across tile boundaries to avoid blocky seams. Applied to the
luminance channel and scaled back onto RGB so hue is preserved.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_LEVELS = 256
_MAX_LEVEL = 255.0
_EPS = 1e-6
DEFAULT_CLIP_LIMIT = 2.0
DEFAULT_TILES = 8


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def apply_clahe(
    arr: np.ndarray,
    clip_limit: float = DEFAULT_CLIP_LIMIT,
    tiles: int = DEFAULT_TILES,
) -> np.ndarray:
    """Return *arr* (HxWx3/4 uint8) with CLAHE applied to its luminance."""
    _validate(arr)
    tiles = max(1, int(tiles))
    rgb = arr[..., :3].astype(np.float32)
    lum = np.clip(np.rint(rgb @ _LUMA_WEIGHTS), 0, 255).astype(np.uint8)
    new_lum = _clahe_plane(lum, max(1.0, float(clip_limit)), tiles)
    ratio = (new_lum.astype(np.float32) + _EPS) / (lum.astype(np.float32) + _EPS)
    out = np.clip(rgb * ratio[..., None], 0, 255)
    result = arr.copy()
    result[..., :3] = np.rint(out).astype(np.uint8)
    return result


def _clahe_plane(plane: np.ndarray, clip_limit: float, tiles: int) -> np.ndarray:
    h, w = plane.shape
    tile_h = int(np.ceil(h / tiles))
    tile_w = int(np.ceil(w / tiles))
    luts = _build_luts(plane, tiles, tile_h, tile_w, clip_limit)
    return _interpolate(plane, luts, tile_h, tile_w)


def _build_luts(plane, tiles, tile_h, tile_w, clip_limit):
    luts = np.empty((tiles, tiles, _LEVELS), dtype=np.float32)
    for ty in range(tiles):
        for tx in range(tiles):
            tile = plane[ty * tile_h:(ty + 1) * tile_h, tx * tile_w:(tx + 1) * tile_w]
            luts[ty, tx] = _tile_lut(tile, clip_limit)
    return luts


def _tile_lut(tile: np.ndarray, clip_limit: float) -> np.ndarray:
    count = tile.size
    if count == 0:
        return np.arange(_LEVELS, dtype=np.float32)
    hist = np.bincount(tile.ravel(), minlength=_LEVELS).astype(np.float32)
    clip = max(1.0, clip_limit * count / _LEVELS)
    excess = np.maximum(hist - clip, 0.0).sum()
    hist = np.minimum(hist, clip) + excess / _LEVELS
    cdf = np.cumsum(hist)
    return (cdf - cdf[0]) / max(cdf[-1] - cdf[0], _EPS) * _MAX_LEVEL


def _interpolate(plane, luts, tile_h, tile_w):
    tiles = luts.shape[0]
    rows = np.arange(plane.shape[0])
    cols = np.arange(plane.shape[1])
    ty0, wy = _tile_coords(rows, tile_h, tiles)
    tx0, wx = _tile_coords(cols, tile_w, tiles)
    ty0, ty1, wy = ty0[:, None], np.minimum(ty0 + 1, tiles - 1)[:, None], wy[:, None]
    tx0, tx1, wx = tx0[None, :], np.minimum(tx0 + 1, tiles - 1)[None, :], wx[None, :]
    val = plane
    top = luts[ty0, tx0, val] * (1 - wx) + luts[ty0, tx1, val] * wx
    bottom = luts[ty1, tx0, val] * (1 - wx) + luts[ty1, tx1, val] * wx
    return np.clip(np.rint(top * (1 - wy) + bottom * wy), 0, 255).astype(np.uint8)


def _tile_coords(indices, tile_size, tiles):
    """Map pixel indices to a fractional tile-centre position."""
    centred = (indices + 0.5) / tile_size - 0.5
    base = np.clip(np.floor(centred), 0, tiles - 1).astype(np.int64)
    frac = np.clip(centred - base, 0.0, 1.0)
    return base, frac.astype(np.float32)
