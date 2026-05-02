"""Pure-numpy automatic colour balancing.

Four classical algorithms, picked at the dialog level via a method
dropdown. None require a neural model, and all run on uint8 RGBA arrays
in place of the recipe pipeline.

* :func:`gray_world` — assume the average colour of the scene is grey
  and rescale each channel so the per-channel mean lands at the overall
  mean luminance.
* :func:`white_patch` — assume the brightest pixel should be pure white
  (max-RGB / Land's white-patch retinex).
* :func:`percentile_stretch` — clip the top and bottom ``percentile`` of
  each channel separately, stretch the remainder to ``[0, 255]``. The
  classic auto-levels move.
* :func:`simplified_retinex` — divide the input by a strongly-blurred
  copy of itself. Single-Scale Retinex; removes colour cast caused by
  uniform illumination.

A high-level :func:`auto_balance` dispatches by method name plus a blend
slider that mixes the corrected output with the original so users can
dial in subtle correction rather than full replace.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.auto_color_balance")

METHODS = ("gray_world", "white_patch", "percentile_stretch", "simplified_retinex")
INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0
PERCENTILE_MIN = 0.0
PERCENTILE_MAX = 10.0
RETINEX_RADIUS_MIN = 4
RETINEX_RADIUS_MAX = 64


@dataclass(frozen=True)
class AutoBalanceOptions:
    """Tuning for :func:`auto_balance`."""

    method: str = "percentile_stretch"
    intensity: float = 1.0     # blend with original
    percentile: float = 1.0    # used by percentile_stretch
    retinex_radius: int = 24   # used by simplified_retinex


def auto_balance(arr: np.ndarray, options: AutoBalanceOptions | None = None) -> np.ndarray:
    """Apply the configured algorithm and blend with the original."""
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"auto_balance expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    options = options or AutoBalanceOptions()
    intensity = max(INTENSITY_MIN, min(INTENSITY_MAX, options.intensity))
    if intensity <= 0.0:
        return arr

    corrected = _dispatch(arr, options)
    if intensity >= 1.0 - 1e-6:
        return corrected
    rgb = arr[..., :3].astype(np.float32)
    corr_rgb = corrected[..., :3].astype(np.float32)
    blended = rgb * (1.0 - intensity) + corr_rgb * intensity
    out = arr.copy()
    out[..., :3] = np.clip(blended, 0, 255).astype(np.uint8)
    return out


def _dispatch(arr: np.ndarray, options: AutoBalanceOptions) -> np.ndarray:
    method = options.method
    if method == "gray_world":
        return gray_world(arr)
    if method == "white_patch":
        return white_patch(arr)
    if method == "percentile_stretch":
        return percentile_stretch(arr, options.percentile)
    if method == "simplified_retinex":
        return simplified_retinex(arr, options.retinex_radius)
    logger.warning("Unknown auto-balance method '%s', returning input", method)
    return arr


# ---------------------------------------------------------------------------
# Algorithms
# ---------------------------------------------------------------------------


def gray_world(arr: np.ndarray) -> np.ndarray:
    """Rescale each channel so the per-channel mean equals the overall luma mean."""
    rgb = arr[..., :3].astype(np.float32)
    means = rgb.reshape(-1, 3).mean(axis=0)
    target = float(means.mean())
    if target <= 1e-3 or (means <= 1e-3).any():
        return arr
    gains = target / means
    rgb_out = rgb * gains[None, None, :]
    out = arr.copy()
    out[..., :3] = np.clip(rgb_out, 0, 255).astype(np.uint8)
    return out


def white_patch(arr: np.ndarray) -> np.ndarray:
    """Rescale each channel so its 99th-percentile equals 255 (max-RGB Retinex).

    Using the 99th percentile rather than the absolute max is more robust
    to a single bright pixel (specular highlight, dust speck) hijacking
    the gain factor.
    """
    rgb = arr[..., :3].astype(np.float32)
    flat = rgb.reshape(-1, 3)
    high = np.percentile(flat, 99, axis=0)
    if (high <= 1e-3).any():
        return arr
    gains = 255.0 / high
    rgb_out = rgb * gains[None, None, :]
    out = arr.copy()
    out[..., :3] = np.clip(rgb_out, 0, 255).astype(np.uint8)
    return out


def percentile_stretch(arr: np.ndarray, percentile: float = 1.0) -> np.ndarray:
    """Auto-levels: clip the bottom / top ``percentile``%, stretch the rest."""
    pct = max(PERCENTILE_MIN, min(PERCENTILE_MAX, float(percentile)))
    rgb = arr[..., :3].astype(np.float32)
    out = arr.copy()
    for ch in range(3):
        plane = rgb[..., ch]
        low = np.percentile(plane, pct)
        high = np.percentile(plane, 100.0 - pct)
        if high - low < 1e-3:
            continue
        stretched = (plane - low) * (255.0 / (high - low))
        out[..., ch] = np.clip(stretched, 0, 255).astype(np.uint8)
    return out


def simplified_retinex(arr: np.ndarray, radius: int = 24) -> np.ndarray:
    """Single-Scale Retinex — divide image by a heavily-blurred copy.

    Removes colour cast from uniform illumination. The blur radius is
    clamped so callers can't accidentally request a 1024-pixel kernel
    on a 100-pixel thumbnail.
    """
    radius = max(RETINEX_RADIUS_MIN, min(RETINEX_RADIUS_MAX, int(radius)))
    rgb = arr[..., :3].astype(np.float32) + 1.0  # avoid log(0)
    blurred = np.empty_like(rgb)
    for ch in range(3):
        blurred[..., ch] = _box_blur_plane(rgb[..., ch], radius)
    # Retinex output: log(I) - log(blur(I)). Re-centre to mid-grey.
    log_diff = np.log(rgb) - np.log(blurred + 1e-3)
    # Map back to [0, 255] via min/max stretch per channel
    out_rgb = np.empty_like(rgb)
    for ch in range(3):
        plane = log_diff[..., ch]
        low, high = float(plane.min()), float(plane.max())
        if high - low < 1e-3:
            out_rgb[..., ch] = rgb[..., ch] - 1.0
            continue
        out_rgb[..., ch] = (plane - low) * (255.0 / (high - low))
    out = arr.copy()
    out[..., :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _box_blur_plane(plane: np.ndarray, radius: int) -> np.ndarray:
    """Edge-replicated box blur via cumulative sum on each axis."""
    kernel = 2 * radius + 1
    padded = np.pad(plane, radius, mode="edge").astype(np.float32)
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
    return blurred / (kernel * kernel)
