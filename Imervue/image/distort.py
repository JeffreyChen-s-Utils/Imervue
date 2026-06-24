"""Geometric distortion filters — swirl, pinch/bulge, ripple.

One-click creative warps for the photo viewer (distinct from the paint
subsystem's interactive liquify brush). Each mode is a reverse map: build the
output coordinate grid, compute where each output pixel samples the source, and
bilinearly resample. Pure NumPy — no scipy — so it ships in the main program.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.resample import (
    RGB_CHANNELS as _RGB_CHANNELS,
    RGBA_CHANNELS as _RGBA_CHANNELS,
    ensure_rgba,
    sample_bilinear,
)

SWIRL = "swirl"
PINCH = "pinch"
RIPPLE = "ripple"
MODES = (SWIRL, PINCH, RIPPLE)

_RIPPLE_AMP_FRAC = 0.03
_RIPPLE_WAVES = 8.0


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def distort(arr: np.ndarray, mode: str, strength: float) -> np.ndarray:
    """Warp *arr* (HxWx3/4 uint8) by *mode*; ``strength`` in [-1, 1]. Returns RGBA."""
    _validate(arr)
    if mode not in MODES:
        raise ValueError(f"unknown distort mode {mode!r}; expected one of {MODES}")
    rgba = ensure_rgba(arr)
    strength = float(np.clip(strength, -1.0, 1.0))
    h, w = rgba.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    sample_x, sample_y = _coords(mode, xx, yy, w, h, strength)
    return sample_bilinear(rgba, sample_x, sample_y)


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
