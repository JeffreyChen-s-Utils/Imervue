"""Tone equalizer — independent exposure control per luminance zone.

darktable's most-praised tonal tool: instead of one global curve, the tonal
range is split into zones spanning roughly -8 EV (deep shadow) to 0 EV
(highlight), and each zone is pushed up or down by its own number of exposure
stops. A pixel's gain is interpolated from the zone whose EV it falls in, so the
adjustment follows the scene's tones rather than fixed pixel values.

To avoid the haloing a per-pixel gain would cause, the luminance that drives the
zone assignment is blurred first (a cheap stand-in for darktable's guided
filter): neighbouring pixels share a gain, so edges keep their local contrast.

Pure NumPy on ``HxWx3/4`` uint8 — ships in the main program. Alpha is preserved.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.local_contrast import blur_plane

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_NEAR_ZERO = 1e-6
_EV_FLOOR = -8.0
_EV_CEIL = 0.0
_GAIN_LIMIT = 4.0
_MIN_ZONES = 2
DEFAULT_SMOOTHING = 12


def zone_gain_map(lum_norm: np.ndarray, zone_gains: tuple[float, ...]) -> np.ndarray:
    """Return a per-pixel gain (in stops) for normalised luminance *lum_norm*.

    *zone_gains* are the stop adjustments from the darkest zone (-8 EV) to the
    brightest (0 EV), evenly spaced; the gain for each pixel is linearly
    interpolated between the surrounding zones in EV space.
    """
    gains = np.clip(np.asarray(zone_gains, dtype=np.float32), -_GAIN_LIMIT, _GAIN_LIMIT)
    floor = np.float32(2.0 ** _EV_FLOOR)
    ev = np.log2(np.maximum(lum_norm.astype(np.float32), floor))
    zone_ev = np.linspace(_EV_FLOOR, _EV_CEIL, gains.size, dtype=np.float32)
    return np.interp(ev, zone_ev, gains).astype(np.float32)


def apply_tone_equalizer(
    arr: np.ndarray,
    zone_gains: tuple[float, ...],
    smoothing: int = DEFAULT_SMOOTHING,
) -> np.ndarray:
    """Return *arr* with per-zone exposure gains applied.

    *zone_gains* is a tuple of stop adjustments (shadows → highlights); at least
    two are required. *smoothing* is the blur radius applied to the luminance
    that drives zone assignment (0 disables it, giving a per-pixel gain).
    """
    _validate(arr, zone_gains)
    if not any(abs(g) > _NEAR_ZERO for g in zone_gains):
        return arr.copy()
    rgb = arr[..., :3].astype(np.float32)
    lum = (rgb @ _LUMA_WEIGHTS) / _MAX_8BIT
    if smoothing > 0:
        lum = blur_plane(lum, smoothing)
    gain = zone_gain_map(np.clip(lum, 0.0, 1.0), zone_gains)
    out = rgb * (2.0 ** gain)[..., None]
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return result


def _validate(arr: np.ndarray, zone_gains: tuple[float, ...]) -> None:
    if (
        arr.ndim != _RGB_CHANNELS
        or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS)
        or arr.dtype != np.uint8
    ):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape} {arr.dtype}")
    if len(zone_gains) < _MIN_ZONES:
        raise ValueError("zone_gains needs at least two zones")
