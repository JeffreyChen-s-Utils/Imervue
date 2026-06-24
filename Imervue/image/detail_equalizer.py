"""Detail equalizer — independent contrast per detail scale.

darktable's *contrast equalizer* / RawTherapee's *Contrast by Detail Levels*:
instead of one clarity slider, the luminance is split into several frequency
bands (fine texture → coarse contrast) and each band is boosted or cut on its
own. Lift the finest band to sharpen pores and foliage while taming the medium
band so the overall contrast stays calm — control the single-scale clarity
operator never gives.

The bands are successive differences of Gaussian blurs (a pyramid of residuals);
each is scaled by its gain and the change is added back to the colour. Pure
NumPy on ``HxWx3/4`` uint8 — ships in the main program. Alpha is preserved.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.local_contrast import blur_plane

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_NEAR_ZERO = 1e-6
_BASE_RADIUS = 2
_GAIN_LIMIT = 8.0


def detail_delta(lum: np.ndarray, band_gains: tuple[float, ...]) -> np.ndarray:
    """Return the luminance change from re-weighting each detail band of *lum*.

    Band ``i`` is ``blur(r_{i-1}) - blur(r_i)`` with geometrically growing radii
    (finest first); the returned delta is ``sum((gain_i - 1) * band_i)``, so a
    gain of 1 leaves a band untouched.
    """
    gains = np.clip(np.asarray(band_gains, dtype=np.float32), -_GAIN_LIMIT, _GAIN_LIMIT)
    delta = np.zeros_like(lum, dtype=np.float32)
    prev = lum.astype(np.float32)
    for index, gain in enumerate(gains):
        radius = _BASE_RADIUS * (2 ** index)
        current = blur_plane(prev, radius)
        delta += (gain - 1.0) * (prev - current)
        prev = current
    return delta


def apply_detail_equalizer(
    arr: np.ndarray, band_gains: tuple[float, ...],
) -> np.ndarray:
    """Return *arr* with per-scale luminance contrast re-weighted.

    *band_gains* lists the gain for each detail band from finest to coarsest; a
    gain of ``1.0`` is neutral, ``>1`` boosts that scale, ``0`` removes it and
    ``<0`` inverts it. At least one band is required.
    """
    _validate(arr, band_gains)
    if all(abs(g - 1.0) < _NEAR_ZERO for g in band_gains):
        return arr.copy()
    rgb = arr[..., :3].astype(np.float32)
    lum = rgb @ _LUMA_WEIGHTS
    delta = detail_delta(lum, band_gains)
    out = rgb + delta[..., None]
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return result


def _validate(arr: np.ndarray, band_gains: tuple[float, ...]) -> None:
    if (
        arr.ndim != _RGB_CHANNELS
        or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS)
        or arr.dtype != np.uint8
    ):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape} {arr.dtype}")
    if len(band_gains) < 1:
        raise ValueError("band_gains needs at least one band")
