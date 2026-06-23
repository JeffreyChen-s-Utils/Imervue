"""Diffuse glow / Orton soft-focus bloom.

Blends a Gaussian-blurred copy of the image back over the original with a
*screen* blend, which only ever lightens — giving the dreamy highlight bloom of
the Orton effect and the soft-focus portrait look. ``threshold`` gates the glow
to brighter-than-threshold regions (Orton's highlight-only bloom); at
``threshold = 0`` the whole frame glows (classic diffuse glow). Pure NumPy on
``HxWx4`` uint8 RGBA (alpha preserved); reuses the project's separable Gaussian.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.local_contrast import blur_plane

_RGBA_CHANNELS = 4
_RGB_CHANNELS = 3
_MAX = 255
_LUMA_WEIGHTS = (0.299, 0.587, 0.114)
_EPS = 1e-6


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != _RGBA_CHANNELS or arr.dtype != np.uint8:
        raise ValueError(f"expected HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}")


def screen_blend(base: np.ndarray, top: np.ndarray) -> np.ndarray:
    """Screen blend two ``[0, 1]`` arrays: ``1 - (1 - base)(1 - top)`` (lightens)."""
    return 1.0 - (1.0 - base) * (1.0 - top)


def _highlight_weight(blurred_rgb: np.ndarray, threshold: float) -> np.ndarray:
    """Per-pixel glow weight gating brighter-than-threshold regions to ``[0, 1]``."""
    if threshold <= 0.0:
        return np.ones(blurred_rgb.shape[:2] + (1,), dtype=np.float32)
    luma = blurred_rgb @ np.asarray(_LUMA_WEIGHTS, dtype=np.float32)
    weight = np.clip((luma - threshold) / max(1.0 - threshold, _EPS), 0.0, 1.0)
    return weight[..., np.newaxis]


def apply_glow(
    arr: np.ndarray,
    amount: float = 0.5,
    radius: int = 15,
    threshold: float = 0.0,
) -> np.ndarray:
    """Return ``arr`` with a soft glow bloom (HxWx4 uint8 RGBA).

    ``amount`` (0-1) is the glow opacity, ``radius`` the blur radius, and
    ``threshold`` (0-1) the brightness above which regions bloom (0 = whole
    frame). The screen blend only lightens, so the result never darkens; alpha
    is preserved. ``amount = 0`` returns an identity copy.
    """
    _validate(arr)
    amount = float(min(1.0, max(0.0, amount)))
    threshold = float(min(1.0, max(0.0, threshold)))
    if not amount:  # clamped to [0, 1]; only an exact zero is a no-op
        return arr.copy()
    base = arr[..., :_RGB_CHANNELS].astype(np.float32) / _MAX
    blurred = np.stack(
        [blur_plane(base[..., c], max(1, int(radius))) for c in range(_RGB_CHANNELS)],
        axis=-1,
    )
    screened = screen_blend(base, blurred)
    opacity = amount * _highlight_weight(blurred, threshold)
    blended = base * (1.0 - opacity) + screened * opacity
    out = arr.copy()
    out[..., :_RGB_CHANNELS] = np.clip(np.rint(blended * _MAX), 0, _MAX).astype(np.uint8)
    return out
