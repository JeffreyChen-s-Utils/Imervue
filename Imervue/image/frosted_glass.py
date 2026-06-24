"""Frosted glass — random local pixel scatter.

Paint.NET's *Frosted Glass* / GIMP's *Spread*: each output pixel is taken from a
random source pixel within a small neighbourhood, jittering detail as if seen
through textured glass. The scatter is driven by a seeded generator, so the
result is deterministic per seed (and reproducible in tests).

Unlike additive noise (``film_grain``) the pixel values themselves are never
invented — every output value already existed somewhere nearby in the source.
Pure NumPy on ``HxWx3/4`` uint8 — ships in the main program. Returns RGBA.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.resample import (
    RGB_CHANNELS as _RGB_CHANNELS,
    RGBA_CHANNELS as _RGBA_CHANNELS,
    ensure_rgba,
)

_RADIUS_LIMIT = 64


def frosted_glass(arr: np.ndarray, radius: int = 4, seed: int = 0) -> np.ndarray:
    """Return *arr* with each pixel replaced by a random neighbour.

    *radius* (clamped to ``[0, 64]``) is the maximum displacement in pixels; 0 is
    an identity copy. *seed* makes the scatter reproducible. Displacements are
    clamped to the image bounds, so edges stay populated.
    """
    _validate(arr)
    radius = int(np.clip(radius, 0, _RADIUS_LIMIT))
    rgba = ensure_rgba(arr)
    if radius == 0:
        return rgba.copy()
    height, width = rgba.shape[:2]
    rng = np.random.default_rng(seed)
    dx = rng.integers(-radius, radius + 1, size=(height, width))
    dy = rng.integers(-radius, radius + 1, size=(height, width))
    yy, xx = np.mgrid[0:height, 0:width]
    src_x = np.clip(xx + dx, 0, width - 1)
    src_y = np.clip(yy + dy, 0, height - 1)
    return rgba[src_y, src_x]


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
