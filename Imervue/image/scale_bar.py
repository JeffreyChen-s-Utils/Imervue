"""Scale-bar overlay with pixel-distance calibration.

For microscopy, macro and forensic/evidence work: once the user calibrates how
many pixels span a known real-world length, this draws a tidy "nice number"
scale bar (1 / 2 / 5 × 10ⁿ units) with a label, so distances in the image are
legible at a glance.

Pure NumPy + Pillow drawing (the same approach as the watermark module).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_TARGET_FRACTION = 1.0 / 6.0   # bar spans ~1/6 of the image width
_NICE_STEPS = (1.0, 2.0, 5.0)
_MARGIN_FRAC = 0.03
_BAR_HEIGHT_FRAC = 0.012
_MIN_BAR_HEIGHT = 3


def nice_length(target_units: float) -> float:
    """Largest 1/2/5×10ⁿ value not exceeding *target_units* (>0)."""
    if target_units <= 0:
        return 1.0
    exponent = np.floor(np.log10(target_units))
    base = 10.0 ** exponent
    for step in reversed(_NICE_STEPS):
        if step * base <= target_units:
            return step * base
    return base


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def _format_label(units: float, unit: str) -> str:
    text = f"{units:.0f}" if units >= 1 else f"{units:g}"
    return f"{text} {unit}"


def add_scale_bar(arr: np.ndarray, px_per_unit: float, unit: str = "um") -> np.ndarray:
    """Draw a calibrated scale bar on *arr* (HxWx3/4 uint8); returns RGBA."""
    _validate(arr)
    if px_per_unit <= 0:
        raise ValueError("px_per_unit must be positive")
    h, w = arr.shape[:2]
    target_units = (w * _TARGET_FRACTION) / px_per_unit
    units = nice_length(target_units)
    bar_px = max(1, int(round(units * px_per_unit)))

    img = Image.fromarray(arr if arr.shape[2] == _RGBA_CHANNELS else
                          np.dstack([arr, np.full((h, w), _OPAQUE, np.uint8)]), "RGBA")
    draw = ImageDraw.Draw(img)
    margin = int(w * _MARGIN_FRAC)
    bar_h = max(_MIN_BAR_HEIGHT, int(h * _BAR_HEIGHT_FRAC))
    x1 = w - margin
    x0 = max(0, x1 - bar_px)
    y1 = h - margin
    y0 = y1 - bar_h
    draw.rectangle([x0 - 1, y0 - 1, x1 + 1, y1 + 1], fill=(0, 0, 0, _OPAQUE))
    draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255, _OPAQUE))
    label = _format_label(units, unit)
    draw.text((x0, y0 - bar_h - 14), label, fill=(255, 255, 255, _OPAQUE),
              font=ImageFont.load_default())
    return np.array(img)
