"""Show 16-bit and floating-point greyscale pictures at their real brightness.

Pillow's ``convert`` clips a 16- or 32-bit greyscale value to 255 instead of
scaling it (Pillow issues #3011, #3159), so a 16-bit greyscale PNG or TIFF -
a scan, a depth map, a scientific or astronomy frame - showed almost white,
and a floating-point TIFF of 0..1 values black. :func:`to_eight_bit` scales
those modes to 8-bit greyscale first; every other mode passes through.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

_SIXTEEN_BIT_MODES = frozenset({"I;16", "I;16L", "I;16B", "I;16N"})
_SIXTEEN_BIT_MAX = 65535


def to_eight_bit(img: Image.Image) -> Image.Image:
    """*img* as 8-bit greyscale ``"L"`` scaled over its real range; other modes unchanged.

    - 16-bit (``I;16`` and its byte orders): the full 0..65535 range.
    - 32-bit integer (``I``): the same when every value fits in 16 bits,
      otherwise stretched from its lowest to its highest value.
    - Floating point (``F``): 0..1 when the values lie there, otherwise
      stretched the same way; NaN and infinities show black.

    The result keeps *img*'s ``info`` (a colour profile, a DPI).
    """
    if img.mode in _SIXTEEN_BIT_MODES:
        values = np.asarray(img).astype(np.uint32)
        grey = (values * 255 + _SIXTEEN_BIT_MAX // 2) // _SIXTEEN_BIT_MAX
    elif img.mode == "I":
        grey = _integer_grey(np.asarray(img))
    elif img.mode == "F":
        grey = _float_grey(np.asarray(img))
    else:
        return img
    out = Image.fromarray(grey.astype(np.uint8), "L")
    out.info = dict(img.info)
    return out


def _integer_grey(values: np.ndarray) -> np.ndarray:
    low, high = int(values.min()), int(values.max())
    if low >= 0 and high <= _SIXTEEN_BIT_MAX:
        return (values.astype(np.int64) * 255 + _SIXTEEN_BIT_MAX // 2) // _SIXTEEN_BIT_MAX
    return _stretch(values.astype(np.float32), float(low), float(high))


def _float_grey(values: np.ndarray) -> np.ndarray:
    finite = np.isfinite(values)
    if not finite.any():
        return np.zeros(values.shape, np.uint8)
    low, high = float(values[finite].min()), float(values[finite].max())
    if low < 0.0 or high > 1.0:
        grey = _stretch(values, low, high)
    else:
        grey = np.rint(values * np.float32(255.0))
    return np.where(finite, grey, 0)


def _stretch(values: np.ndarray, low: float, high: float) -> np.ndarray:
    """Map *low*..*high* linearly onto 0..255; a flat picture shows black."""
    if high <= low:
        return np.zeros(values.shape, np.uint8)
    scale = np.float32(255.0 / (high - low))
    return np.rint((values - np.float32(low)) * scale)
