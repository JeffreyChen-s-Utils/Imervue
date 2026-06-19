"""Encode-size estimation and target-file-size optimization.

Encodes an image to an in-memory buffer to measure the exact byte size at a
given quality, and binary-searches the quality to hit a target file-size
budget — the "fit this under N KB" export that batch convert lacks. Pure
Pillow + stdlib.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_BYTES_PER_KB = 1024.0
_LOSSY_FORMATS = {"JPEG", "WEBP", "AVIF"}
_MIN_QUALITY = 5
_MAX_QUALITY = 95
_SEARCH_STEPS = 8


def _to_pil(arr: np.ndarray) -> Image.Image:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
    mode = "RGBA" if arr.shape[2] == _RGBA_CHANNELS else "RGB"
    img = Image.fromarray(arr, mode)
    return img.convert("RGB") if mode == "RGBA" else img


def _encode(img: Image.Image, fmt: str, quality: int) -> bytes:
    buffer = io.BytesIO()
    params: dict = {"quality": int(quality)}
    if fmt == "JPEG":
        params.update(optimize=True, progressive=True)
    img.save(buffer, format=fmt, **params)
    return buffer.getvalue()


def estimate_size_kb(arr: np.ndarray, fmt: str = "JPEG", quality: int = 85) -> float:
    """Return the encoded size in KB of *arr* at *quality* for *fmt*."""
    fmt = fmt.upper()
    return len(_encode(_to_pil(arr), fmt, quality)) / _BYTES_PER_KB


def encode_to_budget(
    arr: np.ndarray, max_kb: float, fmt: str = "JPEG",
) -> tuple[bytes, int]:
    """Binary-search quality so the encoded size is the largest ≤ *max_kb*.

    Returns ``(encoded_bytes, quality)``. If even the lowest quality exceeds the
    budget, the lowest-quality encoding is returned.
    """
    fmt = fmt.upper()
    if fmt not in _LOSSY_FORMATS:
        raise ValueError(f"target-size encoding needs a lossy format, got {fmt}")
    img = _to_pil(arr)
    budget = max_kb * _BYTES_PER_KB
    low, high = _MIN_QUALITY, _MAX_QUALITY
    best = _encode(img, fmt, low)
    best_q = low
    for _step in range(_SEARCH_STEPS):
        if low > high:
            break
        mid = (low + high) // 2
        data = _encode(img, fmt, mid)
        if len(data) <= budget:
            best, best_q = data, mid
            low = mid + 1
        else:
            high = mid - 1
    return best, best_q
