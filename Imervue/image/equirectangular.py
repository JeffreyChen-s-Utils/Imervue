"""360° equirectangular helpers — "tiny planet" stereographic projection.

A 360°×180° panorama is stored equirectangularly: longitude maps to the x
axis, latitude to the y axis (so the image is twice as wide as tall). This
module reprojects such a panorama into the popular "little planet" view — a
stereographic projection looking straight down, which curls the ground into a
sphere — and exports it as a flat still.

Pure NumPy: build the output sample grid analytically, then bilinearly sample
the panorama (longitude wraps, latitude clamps).
"""
from __future__ import annotations

import numpy as np

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_TWO_PI = 2.0 * np.pi
DEFAULT_SIZE = 800
_ASPECT_TOLERANCE = 0.05


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def is_equirectangular(arr: np.ndarray, tolerance: float = _ASPECT_TOLERANCE) -> bool:
    """True when *arr* has the 2:1 aspect ratio of an equirectangular panorama."""
    _validate(arr)
    h, w = arr.shape[:2]
    if h == 0:
        return False
    return abs(w / (2.0 * h) - 1.0) <= tolerance


def _to_rgba(arr: np.ndarray) -> np.ndarray:
    if arr.shape[2] == _RGBA_CHANNELS:
        return arr
    alpha = np.full((*arr.shape[:2], 1), _OPAQUE, dtype=np.uint8)
    return np.concatenate([arr, alpha], axis=2)


def tiny_planet(arr: np.ndarray, size: int = DEFAULT_SIZE) -> np.ndarray:
    """Reproject equirectangular *arr* into a ``size`` x ``size`` RGBA little planet."""
    _validate(arr)
    rgba = _to_rgba(arr)
    side = max(16, int(size))
    h, w = rgba.shape[:2]

    axis = (np.arange(side) + 0.5) / side * 2.0 - 1.0
    x = axis[None, :]
    y = axis[:, None]
    radius = np.hypot(x, y)
    lon = np.arctan2(y, x)
    lat = 2.0 * np.arctan(radius) - np.pi / 2.0  # centre = nadir (the ground)

    sample_x = (lon / _TWO_PI + 0.5) * w
    sample_y = (0.5 - lat / np.pi) * (h - 1)
    return _sample_bilinear(rgba, np.broadcast_to(sample_x, (side, side)),
                            np.broadcast_to(sample_y, (side, side)))


def _sample_bilinear(rgba: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> np.ndarray:
    h, w = rgba.shape[:2]
    x0 = np.floor(sx).astype(np.int64)
    y0 = np.floor(sy).astype(np.int64)
    fx = (sx - x0)[..., None]
    fy = (sy - y0)[..., None]
    xa, xb = x0 % w, (x0 + 1) % w
    ya = np.clip(y0, 0, h - 1)
    yb = np.clip(y0 + 1, 0, h - 1)
    top = rgba[ya, xa] * (1 - fx) + rgba[ya, xb] * fx
    bottom = rgba[yb, xa] * (1 - fx) + rgba[yb, xb] * fx
    out = top * (1 - fy) + bottom * fy
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)
