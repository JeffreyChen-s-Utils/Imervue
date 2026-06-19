"""Geometric distortion filters — swirl, pinch/bulge, ripple.

One-click creative warps for the photo viewer (distinct from the paint
subsystem's interactive liquify brush). Each mode is a reverse map: build the
output coordinate grid, compute where each output pixel samples the source, and
bilinearly resample. Pure NumPy — no scipy — so it ships in the main program.
"""
from __future__ import annotations

import numpy as np

SWIRL = "swirl"
PINCH = "pinch"
RIPPLE = "ripple"
MODES = (SWIRL, PINCH, RIPPLE)

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_RIPPLE_AMP_FRAC = 0.03
_RIPPLE_WAVES = 8.0


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def _to_rgba(arr: np.ndarray) -> np.ndarray:
    if arr.shape[2] == _RGBA_CHANNELS:
        return arr
    alpha = np.full((*arr.shape[:2], 1), _OPAQUE, dtype=np.uint8)
    return np.concatenate([arr, alpha], axis=2)


def distort(arr: np.ndarray, mode: str, strength: float) -> np.ndarray:
    """Warp *arr* (HxWx3/4 uint8) by *mode*; ``strength`` in [-1, 1]. Returns RGBA."""
    _validate(arr)
    if mode not in MODES:
        raise ValueError(f"unknown distort mode {mode!r}; expected one of {MODES}")
    rgba = _to_rgba(arr)
    strength = float(np.clip(strength, -1.0, 1.0))
    h, w = rgba.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    sample_x, sample_y = _coords(mode, xx, yy, w, h, strength)
    return _sample_bilinear(rgba, sample_x, sample_y)


def _coords(mode, xx, yy, w, h, strength):
    if mode == RIPPLE:
        amp = strength * min(h, w) * _RIPPLE_AMP_FRAC
        wavelength = max(8.0, min(h, w) / _RIPPLE_WAVES)
        return (xx + amp * np.sin(2 * np.pi * yy / wavelength),
                yy + amp * np.sin(2 * np.pi * xx / wavelength))
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    dx, dy = xx - cx, yy - cy
    radius = max(1.0, min(h, w) / 2.0)
    dist = np.hypot(dx, dy)
    if mode == SWIRL:
        decay = np.clip(1.0 - dist / radius, 0.0, 1.0)
        angle = np.arctan2(dy, dx) + strength * np.pi * decay
        return cx + dist * np.cos(angle), cy + dist * np.sin(angle)
    # PINCH: strength > 0 bulges, < 0 pinches; identity outside the radius.
    norm = np.clip(dist / radius, 1e-6, 1.0)
    factor = np.power(norm, -strength)
    inside = dist <= radius
    return (np.where(inside, cx + dx * factor, xx),
            np.where(inside, cy + dy * factor, yy))


def _sample_bilinear(rgba: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> np.ndarray:
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
    return np.clip(np.rint(top * (1 - fy) + bottom * fy), 0, 255).astype(np.uint8)
