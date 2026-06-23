"""Solarize tone reversal — a darkroom-style partial inversion.

Above a luminance-independent per-channel cutoff the tone is inverted
(``255 - v``), below it the tone is kept, producing the classic Sabattier /
solarize look that ``posterize`` (hard threshold) and ``curves`` cannot.
``mix`` blends the reversed result back toward the original so the effect can
be dialled in. Pure NumPy on ``HxWx4`` uint8 RGBA; alpha is preserved.
"""
from __future__ import annotations

import numpy as np

_RGBA_CHANNELS = 4
_LEVELS = 256
_MAX = 255


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != _RGBA_CHANNELS or arr.dtype != np.uint8:
        raise ValueError(f"expected HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}")


def solarize_lut(threshold: float = 0.5, mix: float = 1.0) -> np.ndarray:
    """Return the 256-entry uint8 lookup table for a solarize at *threshold*.

    *threshold* (0-1) is the channel cutoff above which tones invert; *mix*
    (0-1) blends the reversed curve toward the identity. Both are clamped.
    """
    threshold = float(min(1.0, max(0.0, threshold)))
    mix = float(min(1.0, max(0.0, mix)))
    values = np.arange(_LEVELS, dtype=np.float64)
    cutoff = threshold * _MAX
    reversed_curve = np.where(values >= cutoff, _MAX - values, values)
    blended = values * (1.0 - mix) + reversed_curve * mix
    return np.clip(np.rint(blended), 0, _MAX).astype(np.uint8)


def apply_solarize(
    arr: np.ndarray, threshold: float = 0.5, mix: float = 1.0,
) -> np.ndarray:
    """Return a solarized copy of ``arr`` (HxWx4 uint8 RGBA).

    Tones at or above ``threshold`` (0-1) are inverted; ``mix`` (0-1) blends the
    result toward the original (``mix=0`` is an identity copy). Alpha is left
    untouched.
    """
    _validate(arr)
    lut = solarize_lut(threshold, mix)
    out = arr.copy()
    out[..., :3] = lut[arr[..., :3]]
    return out
