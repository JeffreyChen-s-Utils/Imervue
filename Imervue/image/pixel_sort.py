"""Pixel-sorting glitch effect.

Within each row (or column), pixels whose brightness falls inside a threshold
band are sorted by brightness, leaving out-of-band runs untouched — the iconic
Kim-Asendorf glitch look. Pure NumPy: a per-line scan with vectorised span
sorts.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
DEFAULT_LOWER = 60
DEFAULT_UPPER = 200


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def _sort_line(line: np.ndarray, brightness: np.ndarray, lower: float, upper: float) -> None:
    in_band = (brightness >= lower) & (brightness <= upper)
    n = line.shape[0]
    i = 0
    while i < n:
        if not in_band[i]:
            i += 1
            continue
        j = i
        while j < n and in_band[j]:
            j += 1
        order = np.argsort(brightness[i:j], kind="stable")
        line[i:j] = line[i:j][order]
        i = j


def pixel_sort(
    arr: np.ndarray,
    lower: int = DEFAULT_LOWER,
    upper: int = DEFAULT_UPPER,
    *,
    vertical: bool = False,
) -> np.ndarray:
    """Return *arr* (HxWx3/4 uint8) pixel-sorted within brightness bands; RGBA."""
    _validate(arr)
    lower, upper = float(min(lower, upper)), float(max(lower, upper))
    rgba = arr if arr.shape[2] == _RGBA_CHANNELS else np.dstack(
        [arr, np.full(arr.shape[:2], _OPAQUE, dtype=np.uint8)])
    out = rgba.copy()
    work = np.swapaxes(out, 0, 1) if vertical else out
    brightness = (work[..., :3].astype(np.float32) @ _LUMA_WEIGHTS)
    for row in range(work.shape[0]):
        _sort_line(work[row], brightness[row], lower, upper)
    return out
