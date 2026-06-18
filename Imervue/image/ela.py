"""Error Level Analysis — a forensic re-save difference view.

Re-encodes the image to JPEG at a known quality and measures, per pixel, how
much it changed. Regions edited or pasted after the last save compress
differently from the untouched background, so they light up brighter than their
surroundings — a quick authenticity / tamper check.

Pure Pillow + NumPy: one in-memory JPEG round-trip, then an amplified absolute
difference rendered as an image.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
DEFAULT_QUALITY = 90
DEFAULT_SCALE = 15


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape}")


def error_level_analysis(
    arr: np.ndarray, quality: int = DEFAULT_QUALITY, scale: int = DEFAULT_SCALE,
) -> np.ndarray:
    """Return an HxWx4 RGBA error-level-analysis visualisation of *arr*."""
    _validate(arr)
    quality = int(np.clip(quality, 1, 100))
    scale = max(1, int(scale))
    rgb = np.ascontiguousarray(arr[:, :, :3])

    buffer = io.BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as recompressed:
        baseline = np.asarray(recompressed.convert("RGB"), dtype=np.int16)

    diff = np.abs(rgb.astype(np.int16) - baseline)
    amplified = np.clip(diff * scale, 0, 255).astype(np.uint8)
    out = np.empty((*rgb.shape[:2], _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = amplified
    out[..., 3] = _OPAQUE
    return out
