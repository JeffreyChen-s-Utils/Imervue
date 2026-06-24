"""Defringe — remove coloured fringes from high-contrast edges.

Axial (longitudinal) chromatic aberration leaves purple/magenta or green halos
along the high-contrast edges of fast lenses wide open. darktable and Lightroom
fix it the same way: find the strong luminance edges, decide whether each edge
pixel carries the offending hue, and pull only those pixels' chroma toward their
luminance — desaturating the fringe while leaving genuine colour untouched.

Pure NumPy on ``HxWx3/4`` uint8 — ships in the main program. Alpha is preserved.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_NEAR_ZERO = 1e-6

PURPLE = "purple"
GREEN = "green"
ALL = "all"
_HUE_MODES = (PURPLE, GREEN, ALL)


def apply_defringe(
    arr: np.ndarray,
    amount: float = 1.0,
    edge_threshold: float = 0.1,
    hue: str = PURPLE,
) -> np.ndarray:
    """Return *arr* with coloured edge fringes desaturated.

    *amount* in ``[0, 1]`` is the maximum desaturation applied. *edge_threshold*
    in ``(0, 1]`` is the luminance-gradient fraction above which a pixel counts
    as an edge (smaller catches softer edges). *hue* selects which fringe colour
    to target: ``"purple"``, ``"green"`` or ``"all"``.
    """
    _validate(arr, hue)
    amount = float(np.clip(amount, 0.0, 1.0))
    if amount < _NEAR_ZERO:
        return arr.copy()
    rgb = arr[..., :3].astype(np.float32)
    lum = rgb @ _LUMA_WEIGHTS
    mask = _edge_weight(lum, edge_threshold) * _fringe_weight(rgb, hue) * amount
    out = rgb + (lum[..., None] - rgb) * mask[..., None]
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return result


def _edge_weight(lum: np.ndarray, edge_threshold: float) -> np.ndarray:
    """Luminance-gradient magnitude mapped to ``[0, 1]`` against the threshold."""
    grad_y, grad_x = np.gradient(lum)
    magnitude = np.hypot(grad_x, grad_y)
    scale = max(edge_threshold, _NEAR_ZERO) * _MAX_8BIT
    return np.clip(magnitude / scale, 0.0, 1.0)


def _fringe_weight(rgb: np.ndarray, hue: str) -> np.ndarray:
    """How strongly each pixel carries the targeted fringe hue, in ``[0, 1]``."""
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    magenta = ((red + blue) * 0.5 - green) / _MAX_8BIT      # purple/violet excess
    greenish = (green - (red + blue) * 0.5) / _MAX_8BIT     # green excess
    if hue == PURPLE:
        weight = magenta
    elif hue == GREEN:
        weight = greenish
    else:
        weight = np.maximum(magenta, greenish)
    return np.clip(weight, 0.0, 1.0)


def _validate(arr: np.ndarray, hue: str) -> None:
    if (
        arr.ndim != _RGB_CHANNELS
        or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS)
        or arr.dtype != np.uint8
    ):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape} {arr.dtype}")
    if hue not in _HUE_MODES:
        raise ValueError(f"hue must be one of {_HUE_MODES}, got {hue!r}")
