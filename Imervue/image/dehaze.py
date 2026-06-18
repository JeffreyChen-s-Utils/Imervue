"""Dehaze — dark-channel-prior atmospheric haze removal.

Hazy / foggy scenes lose contrast and colour because airlight scatters into
every pixel. The dark-channel prior (He, Sun & Tang, 2009) observes that in a
haze-free outdoor patch at least one RGB channel is near zero; where that
"dark channel" is bright, the pixel is hazy. We estimate the airlight and a
per-pixel transmission from the dark channel, then invert the scattering model
``I = J·t + A·(1 − t)`` to recover the scene radiance ``J``.

Pure NumPy — a separable min-filter for the dark channel plus a Gaussian
smoothing of the transmission map to suppress halos — so it ships in the main
program rather than pulling in OpenCV.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.local_contrast import blur_plane

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_PATCH_RADIUS = 7
_OMEGA = 0.95
_MIN_TRANSMISSION = 0.1
_AIRLIGHT_FRACTION = 0.001
_MIN_AIRLIGHT = 0.1


def dehaze(arr: np.ndarray, strength: float) -> np.ndarray:
    """Remove haze from ``arr`` (HxWx3/4 uint8). ``strength`` in [0, 1]."""
    _validate(arr)
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength == 0.0:
        return arr.copy()
    rgb = arr[..., :3].astype(np.float32) / _MAX_8BIT
    airlight = _atmospheric_light(rgb)
    transmission = _transmission(rgb, airlight, strength)
    recovered = (rgb - airlight) / transmission[..., None] + airlight
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(recovered * _MAX_8BIT), 0, 255).astype(np.uint8)
    return result


def _dark_channel(rgb: np.ndarray) -> np.ndarray:
    return _min_filter(rgb.min(axis=2), _PATCH_RADIUS)


def _atmospheric_light(rgb: np.ndarray) -> np.ndarray:
    """The colour of the haze — brightest pixels within the haziest region."""
    dark = _dark_channel(rgb).ravel()
    count = max(1, int(dark.size * _AIRLIGHT_FRACTION))
    haziest = np.argpartition(dark, -count)[-count:]
    airlight = rgb.reshape(-1, _RGB_CHANNELS)[haziest].max(axis=0)
    return np.maximum(airlight, _MIN_AIRLIGHT)


def _transmission(rgb: np.ndarray, airlight: np.ndarray, strength: float) -> np.ndarray:
    omega = _OMEGA * strength
    raw = 1.0 - omega * _dark_channel(rgb / airlight)
    smoothed = blur_plane(raw, _PATCH_RADIUS)
    return np.clip(smoothed, _MIN_TRANSMISSION, 1.0)


def _min_filter(plane: np.ndarray, radius: int) -> np.ndarray:
    return _min_axis(_min_axis(plane, radius, 0), radius, 1)


def _min_axis(plane: np.ndarray, radius: int, axis: int) -> np.ndarray:
    pad_width = [(0, 0), (0, 0)]
    pad_width[axis] = (radius, radius)
    padded = np.pad(plane, pad_width, mode="edge")
    out: np.ndarray | None = None
    for off in range(2 * radius + 1):
        sl = [slice(None), slice(None)]
        sl[axis] = slice(off, off + plane.shape[axis])
        window = padded[tuple(sl)]
        out = window if out is None else np.minimum(out, window)
    return out


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
