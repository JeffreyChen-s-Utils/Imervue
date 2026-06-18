"""HSL / Colour Mixer — per-band hue, saturation and luminance control.

The bedrock selective-colour tool in Lightroom (HSL panel), Capture One
(Colour Editor) and darktable (colour equaliser): split the hue wheel into
eight bands (red → magenta) and let each band's hue, saturation and luminance
be tuned independently. A pixel is affected in proportion to how close its hue
sits to each band centre (smooth cosine falloff), so adjustments blend without
banding.

Pure NumPy — a vectorised RGB↔HSV round-trip — so it ships in the main program.
"""
from __future__ import annotations

import numpy as np

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_HUE_MAX = 360.0
_HUE_SHIFT_RANGE = 30.0   # degrees at full hue slider
_FALLOFF = 45.0           # band half-width in degrees

# (name, centre-hue) — the eight Lightroom HSL bands.
BANDS = (
    ("red", 0.0),
    ("orange", 30.0),
    ("yellow", 60.0),
    ("green", 120.0),
    ("aqua", 180.0),
    ("blue", 240.0),
    ("purple", 285.0),
    ("magenta", 320.0),
)
_ZERO = (0.0, 0.0, 0.0)


def apply_hsl(arr: np.ndarray, adjustments: dict[str, tuple[float, float, float]]) -> np.ndarray:
    """Apply per-band ``(hue, saturation, luminance)`` adjustments to *arr*.

    Each amount is in ``[-1, 1]``. ``adjustments`` maps a band name from
    :data:`BANDS` to its triple; absent or all-zero bands are left untouched.
    """
    _validate(arr)
    active = {b: v for b, v in adjustments.items() if v != _ZERO}
    if not active:
        return arr.copy()
    rgb = arr[..., :3].astype(np.float32) / _MAX_8BIT
    hue, sat, val = _rgb_to_hsv(rgb)
    hue, sat, val = _mix_bands(hue, sat, val, active)
    out = _hsv_to_rgb(hue % _HUE_MAX, np.clip(sat, 0, 1), np.clip(val, 0, 1))
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out * _MAX_8BIT), 0, 255).astype(np.uint8)
    return result


def _mix_bands(hue, sat, val, active):
    hue_delta = np.zeros_like(hue)
    sat_factor = np.ones_like(sat)
    val_factor = np.ones_like(val)
    centres = dict(BANDS)
    for band, (hue_amt, sat_amt, lum_amt) in active.items():
        weight = _band_weight(hue, centres[band])
        hue_delta += weight * hue_amt * _HUE_SHIFT_RANGE
        sat_factor *= 1.0 + weight * sat_amt
        val_factor *= 1.0 + weight * lum_amt
    return hue + hue_delta, sat * sat_factor, val * val_factor


def _band_weight(hue: np.ndarray, centre: float) -> np.ndarray:
    """Cosine-falloff membership of each pixel hue in the band at *centre*."""
    dist = np.abs(hue - centre)
    dist = np.minimum(dist, _HUE_MAX - dist)
    inside = dist < _FALLOFF
    weight = np.cos(np.pi / 2.0 * dist / _FALLOFF) ** 2
    return np.where(inside, weight, 0.0)


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def _rgb_to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    diff = mx - mn
    safe = np.where(diff < 1e-12, 1.0, diff)
    hue = np.select(
        [mx == r, mx == g, mx == b],
        [((g - b) / safe) % 6.0, ((b - r) / safe) + 2.0, ((r - g) / safe) + 4.0],
        default=0.0,
    ) * 60.0
    hue = np.where(diff < 1e-12, 0.0, hue)
    sat = np.where(mx <= 0.0, 0.0, diff / np.where(mx <= 0.0, 1.0, mx))
    return hue, sat, mx


def _hsv_to_rgb(hue: np.ndarray, sat: np.ndarray, val: np.ndarray) -> np.ndarray:
    c = val * sat
    hp = hue / 60.0
    x = c * (1.0 - np.abs(hp % 2.0 - 1.0))
    zero = np.zeros_like(hue)
    sextant = np.floor(hp).astype(int) % 6
    reds = np.select([sextant == i for i in range(6)], [c, x, zero, zero, x, c])
    greens = np.select([sextant == i for i in range(6)], [x, c, c, x, zero, zero])
    blues = np.select([sextant == i for i in range(6)], [zero, zero, x, c, c, x])
    m = val - c
    return np.stack([reds + m, greens + m, blues + m], axis=-1)
