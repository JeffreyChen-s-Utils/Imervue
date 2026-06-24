"""Velvia — luminance-weighted saturation boost (the slide-film look).

The classic Fujichrome Velvia punch, as offered by RawTherapee and darktable.
Unlike a flat saturation/vibrance slider, velvia intensifies *muted* colours
the most while leaving already-saturated ones alone, and weights the effect by
luminance so deep shadows (and, by extension, skin tones in low light) are
protected from over-cooking.

Each pixel is pushed away from its own luminance grey by a gain that rises for
low-saturation pixels and is scaled down in the shadows. Pure NumPy on
``HxWx3/4`` uint8 — ships in the main program. Alpha is preserved.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_NEAR_ZERO = 1e-6
_STRENGTH_MIN = -1.0
_STRENGTH_MAX = 4.0


def apply_velvia(
    arr: np.ndarray, strength: float = 1.0, luminance_protection: float = 0.5,
) -> np.ndarray:
    """Return *arr* with a luminance-weighted saturation boost.

    *strength* (clamped to ``[-1, 4]``) scales the boost; negative desaturates.
    *luminance_protection* in ``[0, 1]`` is how strongly the shadows are spared
    (0 applies the boost evenly, 1 limits it almost entirely to the highlights).
    """
    _validate(arr)
    strength = float(np.clip(strength, _STRENGTH_MIN, _STRENGTH_MAX))
    if abs(strength) < _NEAR_ZERO:
        return arr.copy()
    rgb = arr[..., :3].astype(np.float32)
    gain = _saturation_gain(rgb, strength, float(np.clip(luminance_protection, 0.0, 1.0)))
    grey = (rgb @ _LUMA_WEIGHTS)[..., None]
    out = grey + (rgb - grey) * gain[..., None]
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return result


def _saturation_gain(rgb: np.ndarray, strength: float, protection: float) -> np.ndarray:
    """Per-pixel saturation multiplier: more for muted colours, less in shadows."""
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    sat = (mx - mn) / np.maximum(mx, _NEAR_ZERO)   # 0 (grey) .. 1 (pure)
    muted_weight = 1.0 - sat                        # boost low-saturation pixels more
    lum_norm = (rgb @ _LUMA_WEIGHTS) / _MAX_8BIT
    shadow_weight = (1.0 - protection) + protection * lum_norm
    return 1.0 + strength * muted_weight * shadow_weight


def _validate(arr: np.ndarray) -> None:
    if (
        arr.ndim != _RGB_CHANNELS
        or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS)
        or arr.dtype != np.uint8
    ):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape} {arr.dtype}")
