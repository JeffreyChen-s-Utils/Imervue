"""Subject-isolated background blur (a.k.a. portrait mode).

Given an input image and a subject alpha mask (typically from rembg /
U²-Net), apply a Gaussian blur to the background and composite the
sharp subject back on top. Works on uint8 RGBA arrays — no Qt, no
plugin imports — so the pipeline can be tested directly.

The mask is expected to be a single-channel uint8 array shaped
``(H, W)`` where 255 = subject and 0 = background. The compositor
softens the mask edge with a small feather to avoid hard halos.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.portrait_blur")

BLUR_RADIUS_MIN = 1
BLUR_RADIUS_MAX = 64
FEATHER_RADIUS_MIN = 0
FEATHER_RADIUS_MAX = 16


@dataclass(frozen=True)
class PortraitBlurOptions:
    """Tuneable knobs for :func:`apply_portrait_blur`."""

    blur_radius: int = 16
    feather_radius: int = 4


def apply_portrait_blur(
    arr: np.ndarray,
    mask: np.ndarray,
    options: PortraitBlurOptions | None = None,
) -> np.ndarray:
    """Composite a sharp subject (where ``mask`` is 255) onto a blurred BG."""
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"apply_portrait_blur expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    if mask.ndim != 2 or mask.shape[:2] != arr.shape[:2] or mask.dtype != np.uint8:
        raise ValueError(
            f"mask must match image shape and be uint8 HxW, got {mask.shape} {mask.dtype}"
        )
    options = options or PortraitBlurOptions()
    blur_radius = max(BLUR_RADIUS_MIN, min(BLUR_RADIUS_MAX, options.blur_radius))
    feather = max(FEATHER_RADIUS_MIN, min(FEATHER_RADIUS_MAX, options.feather_radius))

    blurred_rgb = _box_blur_rgb(arr[..., :3], blur_radius)
    soft_mask = _feather_mask(mask, feather)
    alpha = soft_mask.astype(np.float32) / 255.0
    sharp_rgb = arr[..., :3].astype(np.float32)
    blurred_rgb_f = blurred_rgb.astype(np.float32)
    composite = (
        sharp_rgb * alpha[..., None]
        + blurred_rgb_f * (1.0 - alpha[..., None])
    )
    out = arr.copy()
    out[..., :3] = np.clip(composite, 0.0, 255.0).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _box_blur_rgb(rgb: np.ndarray, radius: int) -> np.ndarray:
    """Cheap separable box blur per channel via cumulative sum."""
    if radius <= 0:
        return rgb.copy()
    blurred = np.empty_like(rgb)
    for channel in range(3):
        blurred[..., channel] = _box_blur_plane(rgb[..., channel], radius)
    return blurred


def _box_blur_plane(plane: np.ndarray, radius: int) -> np.ndarray:
    """Edge-replicated box blur via cumulative sum on each axis."""
    kernel = 2 * radius + 1
    padded = np.pad(plane, radius, mode="edge").astype(np.float32)
    # Prepend one zero-row + zero-column to the cumsum so the
    # ``csum[k+kernel] - csum[k]`` form returns full-height output.
    rows = np.concatenate(
        [np.zeros((1, padded.shape[1]), dtype=np.float32), padded],
        axis=0,
    )
    rows_cumsum = np.cumsum(rows, axis=0)
    rows_blurred = rows_cumsum[kernel:, :] - rows_cumsum[:-kernel, :]

    cols = np.concatenate(
        [np.zeros((rows_blurred.shape[0], 1), dtype=np.float32), rows_blurred],
        axis=1,
    )
    cols_cumsum = np.cumsum(cols, axis=1)
    blurred = cols_cumsum[:, kernel:] - cols_cumsum[:, :-kernel]

    return np.clip(blurred / (kernel * kernel) + 0.5, 0, 255).astype(np.uint8)


def _feather_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """Soften a binary mask edge with a small box-blur feather."""
    if radius <= 0:
        return mask
    return _box_blur_plane(mask, radius)
