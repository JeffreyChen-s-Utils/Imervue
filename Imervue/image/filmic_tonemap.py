"""Filmic tone mapping — pure-NumPy highlight rolloff and shadow lift.

A global display-mapping operator for high-contrast single exposures, the case
the OpenCV-backed HDR merge doesn't cover. Luminance is exposure-scaled, run
through a Reinhard or Hable (Uncharted 2) filmic curve to compress highlights
into a soft rolloff, and the colour channels are re-scaled by the same ratio so
hue is preserved. A pivoted contrast control and a saturation restore finish it.

Pure NumPy on ``HxWx3/4`` uint8 — ships in the main program. Alpha is preserved.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_NEAR_ZERO = 1e-6
_MID_GREY = 0.18
_EXPOSURE_LIMIT = 6.0

REINHARD = "reinhard"
HABLE = "hable"
_MODES = (REINHARD, HABLE)

# Uncharted 2 (Hable) filmic constants.
_HABLE = (0.15, 0.50, 0.10, 0.20, 0.02, 0.30)


def apply_filmic_tonemap(
    arr: np.ndarray,
    exposure: float = 0.0,
    white_point: float = 4.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    mode: str = REINHARD,
) -> np.ndarray:
    """Return *arr* tone-mapped with a filmic highlight rolloff.

    *exposure* (stops, clamped to ``[-6, 6]``) pre-scales the image. *white_point*
    is the luminance that maps to white. *contrast* applies a power pivoted on
    mid-grey. *saturation* scales colour after mapping (``0`` is greyscale).
    *mode* selects the ``"reinhard"`` or ``"hable"`` curve.
    """
    _validate(arr, mode)
    exposure = float(np.clip(exposure, -_EXPOSURE_LIMIT, _EXPOSURE_LIMIT))
    white_point = max(float(white_point), _NEAR_ZERO)
    lin = (arr[..., :3].astype(np.float32) / _MAX_8BIT) * (2.0 ** exposure)
    lum = lin @ _LUMA_WEIGHTS
    target = _tone_curve(_apply_contrast(lum, contrast), white_point, mode)
    gain = target / np.maximum(lum, _NEAR_ZERO)
    out = lin * gain[..., None]
    out = _apply_saturation(out, float(np.clip(saturation, 0.0, 4.0)))
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out * _MAX_8BIT), 0, 255).astype(np.uint8)
    return result


def _apply_contrast(lum: np.ndarray, contrast: float) -> np.ndarray:
    if abs(contrast - 1.0) < _NEAR_ZERO:
        return lum
    ratio = np.maximum(lum, _NEAR_ZERO) / _MID_GREY
    return _MID_GREY * np.power(ratio, max(contrast, _NEAR_ZERO))


def _tone_curve(lum: np.ndarray, white_point: float, mode: str) -> np.ndarray:
    if mode == HABLE:
        return _hable(lum) / _hable(np.float32(white_point))
    # Extended Reinhard: maps 0 -> 0 and white_point -> ~1 with a soft rolloff.
    return lum * (1.0 + lum / (white_point * white_point)) / (1.0 + lum)


def _hable(x: np.ndarray) -> np.ndarray:
    a, b, c, d, e, f = _HABLE
    return ((x * (a * x + c * b) + d * e) / (x * (a * x + b) + d * f)) - e / f


def _apply_saturation(rgb: np.ndarray, saturation: float) -> np.ndarray:
    if abs(saturation - 1.0) < _NEAR_ZERO:
        return rgb
    grey = (rgb @ _LUMA_WEIGHTS)[..., None]
    return grey + (rgb - grey) * saturation


def _validate(arr: np.ndarray, mode: str) -> None:
    if (
        arr.ndim != _RGB_CHANNELS
        or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS)
        or arr.dtype != np.uint8
    ):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape} {arr.dtype}")
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {_MODES}, got {mode!r}")
