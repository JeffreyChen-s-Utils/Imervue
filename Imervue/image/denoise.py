"""Noise reduction and sharpening.

Two complementary operations:

- ``reduce_noise``: bilateral filter on the luminance channel preserves
  edges while flattening noise — cheap (~O(N·k²) with separable
  approximations in OpenCV) and shader-like in results.
- ``sharpen``: unsharp mask — subtract a blurred copy from the original
  to boost local contrast around edges.

Both return a new HxWx4 RGBA uint8 array.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("Imervue.denoise")

_MAX_NR_STRENGTH = 1.0
_MAX_SHARPEN_AMOUNT = 3.0


def reduce_noise(
    arr: np.ndarray,
    strength: float = 0.5,
    preserve_color: bool = True,
) -> np.ndarray:
    """Apply edge-preserving noise reduction. *strength* in ``[0, 1]``."""
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("reduce_noise expects HxWx4 RGBA uint8")
    strength = max(0.0, min(_MAX_NR_STRENGTH, float(strength)))
    if strength < 1e-4:
        return arr

    import cv2
    bgr = arr[..., [2, 1, 0]].copy()
    diameter = int(5 + 8 * strength)  # 5..13
    sigma_color = 15.0 + 80.0 * strength
    sigma_space = 15.0 + 80.0 * strength
    if preserve_color:
        filtered = cv2.bilateralFilter(bgr, diameter, sigma_color, sigma_space)
    else:
        # Luminance-only NR: filter Y, keep CbCr.
        ycc = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        ycc[..., 0] = cv2.bilateralFilter(
            ycc[..., 0], diameter, sigma_color, sigma_space,
        )
        filtered = cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR)
    out = arr.copy()
    out[..., 0] = filtered[..., 2]
    out[..., 1] = filtered[..., 1]
    out[..., 2] = filtered[..., 0]
    return out


def sharpen(
    arr: np.ndarray,
    amount: float = 1.0,
    radius: float = 1.5,
    threshold: int = 0,
) -> np.ndarray:
    """Unsharp mask. *amount* is 0..3, *radius* is blur sigma (px)."""
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("sharpen expects HxWx4 RGBA uint8")
    amount = max(0.0, min(_MAX_SHARPEN_AMOUNT, float(amount)))
    if amount < 1e-4:
        return arr

    import cv2
    rgb = arr[..., :3].astype(np.float32)
    ksize = max(3, int(2 * round(3 * radius) + 1))
    blurred = cv2.GaussianBlur(rgb, (ksize, ksize), max(0.1, float(radius)))
    detail = rgb - blurred
    if threshold > 0:
        mask = np.abs(detail).max(axis=-1, keepdims=True) >= threshold
        detail = detail * mask
    sharp = rgb + amount * detail
    np.clip(sharp, 0.0, 255.0, out=sharp)
    out = arr.copy()
    out[..., :3] = sharp.astype(np.uint8)
    return out
