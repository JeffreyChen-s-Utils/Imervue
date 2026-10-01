"""
Per-channel tonal adjustments used by ``Recipe.apply``.

Separated from ``recipe.py`` so that the slider math (white balance, tonal
regions, vibrance) can grow without the core recipe module creeping past
the 1000-line cap. These are all pure numpy functions \u2014 they take an
``HxWx4 uint8`` array and a float adjustment in the conventional
``[-1, +1]`` range and return a new array.
"""
from __future__ import annotations

import math

import numpy as np

_ADJUST_EPS = 1e-6
_MAX_BYTE = 255.0
# Coefficients used for perceptual luminance (Rec.709).
_LUMA_R, _LUMA_G, _LUMA_B = 0.2126, 0.7152, 0.0722


def is_zero(value: float) -> bool:
    """Return True if ``value`` is within float rounding tolerance of zero."""
    return math.isclose(value, 0.0, abs_tol=_ADJUST_EPS)


def apply_white_balance(
    arr: np.ndarray, temperature: float, tint: float,
) -> np.ndarray:
    """Warm/cool and green/magenta shift.

    ``temperature`` > 0 warms the image (more red, less blue) like nudging
    a raw's Kelvin slider up. ``tint`` > 0 pushes toward magenta, < 0 pushes
    toward green.
    """
    if is_zero(temperature) and is_zero(tint):
        return arr
    rgb = arr[..., :3].astype(np.float32)
    temp_gain = 1.0 + temperature * 0.4
    temp_loss = 1.0 - temperature * 0.4
    rgb[..., 0] *= temp_gain
    rgb[..., 2] *= temp_loss
    tint_shift = 1.0 + tint * 0.3
    rgb[..., 1] *= 1.0 / tint_shift if tint_shift > 0 else 1.0
    np.clip(rgb, 0.0, _MAX_BYTE, out=rgb)
    out = arr.copy()
    out[..., :3] = rgb.astype(np.uint8)
    return out


def apply_highlights_shadows(
    arr: np.ndarray, highlights: float, shadows: float,
) -> np.ndarray:
    """Recover highlights / lift shadows by modulating luminance-weighted gain.

    - ``highlights`` < 0 darkens bright pixels (recover burned sky).
    - ``shadows`` > 0 brightens dark pixels (lift blocked shadows).
    """
    if is_zero(highlights) and is_zero(shadows):
        return arr
    rgb = arr[..., :3].astype(np.float32)
    luma = (
        _LUMA_R * rgb[..., 0] + _LUMA_G * rgb[..., 1] + _LUMA_B * rgb[..., 2]
    ) / _MAX_BYTE
    shadow_weight = 1.0 - luma
    highlight_weight = luma
    shadow_gain = 1.0 + shadows * shadow_weight[..., None] * 0.8
    highlight_gain = 1.0 + highlights * highlight_weight[..., None] * 0.8
    rgb *= shadow_gain * highlight_gain
    np.clip(rgb, 0.0, _MAX_BYTE, out=rgb)
    out = arr.copy()
    out[..., :3] = rgb.astype(np.uint8)
    return out


def apply_whites_blacks(
    arr: np.ndarray, whites: float, blacks: float,
) -> np.ndarray:
    """Move the two ends of the tonal range.

    ``whites`` > 0 stretches bright pixels up to 255 and < 0 dims white to a
    grey; ``blacks`` < 0 crushes dark pixels down to 0 and > 0 lifts black to
    a faded grey. Both apply as one linear remap, so mid-tones move least.
    """
    if is_zero(whites) and is_zero(blacks):
        return arr
    # The input tones that land on the ends: a stretch (whites > 0) or a crush (blacks < 0).
    black_in = max(0.0, blacks * -0.2)
    white_in = min(1.0, 1.0 - whites * 0.2)
    # Where the ends land: dimmed (whites < 0) or lifted (blacks > 0). Without
    # these the left half of Whites and the right half of Blacks did nothing.
    black_out = max(0.0, blacks * 0.2)
    white_out = min(1.0, 1.0 + whites * 0.2)
    if white_in - black_in <= 0.01:
        return arr
    rgb = arr[..., :3].astype(np.float32) / _MAX_BYTE
    rgb = black_out + (rgb - black_in) * ((white_out - black_out) / (white_in - black_in))
    np.clip(rgb, 0.0, 1.0, out=rgb)
    out = arr.copy()
    out[..., :3] = (rgb * _MAX_BYTE).astype(np.uint8)
    return out


def apply_vibrance(arr: np.ndarray, vibrance: float) -> np.ndarray:
    """Saturation-aware colour boost \u2014 leaves already-saturated pixels alone.

    Converts to HSV, multiplies saturation by a factor that falls off as
    the pixel is already saturated. This is the classic vibrance
    trick \u2014 it protects skin tones and highly-coloured regions from the
    harsh over-saturation you'd get from the plain saturation slider.
    """
    if is_zero(vibrance):
        return arr
    rgb = arr[..., :3].astype(np.float32) / _MAX_BYTE
    max_c = np.max(rgb, axis=2)
    min_c = np.min(rgb, axis=2)
    delta = max_c - min_c
    sat = np.where(max_c > 0.0, delta / np.maximum(max_c, 1e-6), 0.0)
    gain = 1.0 + vibrance * (1.0 - sat)
    gray = (rgb[..., 0] + rgb[..., 1] + rgb[..., 2]) / 3.0
    rgb = gray[..., None] + (rgb - gray[..., None]) * gain[..., None]
    np.clip(rgb, 0.0, 1.0, out=rgb)
    out = arr.copy()
    out[..., :3] = (rgb * _MAX_BYTE).astype(np.uint8)
    return out
