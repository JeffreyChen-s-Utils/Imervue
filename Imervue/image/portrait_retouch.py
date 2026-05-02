"""Procedural portrait auto-retouch — skin smoothing, red-eye, eye sharpen.

A combination of three passes that together approximate a "beauty mode":

* :func:`smooth_skin` — bilateral-style smoothing constrained to skin-tone
  pixels. Preserves edges so eyebrows and lip lines stay sharp.
* :func:`fix_red_eye` — desaturate and darken pixels with extreme red
  dominance and high luminance, the classic red-eye signature.
* :func:`sharpen_region` — local unsharp mask used to bring eyes back
  into focus after the skin-smoothing pass.

All three operations are pure numpy. Each can run independently or be
chained via :func:`auto_retouch`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.portrait_retouch")

INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0
SMOOTH_RADIUS_MIN = 1
SMOOTH_RADIUS_MAX = 12


@dataclass(frozen=True)
class RetouchOptions:
    """Per-pass intensity sliders for ``auto_retouch``."""

    skin_smooth: float = 0.4
    skin_radius: int = 4
    red_eye: float = 0.6
    eye_sharpen: float = 0.3


def auto_retouch(arr: np.ndarray, options: RetouchOptions | None = None) -> np.ndarray:
    """Run skin smooth → red-eye fix → eye sharpen as one cumulative pass."""
    options = options or RetouchOptions()
    _validate_rgba(arr)
    out = arr
    if options.skin_smooth > 0.0:
        out = smooth_skin(out, options.skin_smooth, options.skin_radius)
    if options.red_eye > 0.0:
        out = fix_red_eye(out, options.red_eye)
    if options.eye_sharpen > 0.0:
        out = sharpen_region(out, options.eye_sharpen)
    return out


# ---------------------------------------------------------------------------
# Skin smoothing
# ---------------------------------------------------------------------------


def smooth_skin(arr: np.ndarray, intensity: float, radius: int = 4) -> np.ndarray:
    """Blend the original RGB with a blurred copy on skin-tone pixels."""
    _validate_rgba(arr)
    intensity = _clamp(intensity, INTENSITY_MIN, INTENSITY_MAX)
    radius = max(SMOOTH_RADIUS_MIN, min(SMOOTH_RADIUS_MAX, int(radius)))
    if intensity <= 0.0:
        return arr
    skin_mask = _skin_tone_mask(arr).astype(np.float32) * intensity
    blurred = _box_blur_rgb(arr[..., :3], radius).astype(np.float32)
    rgb = arr[..., :3].astype(np.float32)
    blended = rgb * (1.0 - skin_mask[..., None]) + blurred * skin_mask[..., None]
    out = arr.copy()
    out[..., :3] = np.clip(blended, 0, 255).astype(np.uint8)
    return out


def _skin_tone_mask(arr: np.ndarray) -> np.ndarray:
    """Heuristic skin-tone mask in HSV-style space, returns float32 in [0, 1]."""
    rgb = arr[..., :3].astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # Classic skin-tone constraints: red dominates, R > B, in the warm range.
    cond = (
        (r > 95) & (g > 40) & (b > 20)
        & (r > g) & (r > b)
        & (np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b) > 15)
        & (np.abs(r - g) > 15)
    )
    return cond.astype(np.float32)


# ---------------------------------------------------------------------------
# Red-eye removal
# ---------------------------------------------------------------------------


def fix_red_eye(arr: np.ndarray, intensity: float) -> np.ndarray:
    """Darken + desaturate pixels that match the red-eye signature."""
    _validate_rgba(arr)
    intensity = _clamp(intensity, INTENSITY_MIN, INTENSITY_MAX)
    if intensity <= 0.0:
        return arr
    rgb = arr[..., :3].astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # Red-eye pixels: R is at least 1.5× max(G, B), and R is bright.
    other_max = np.maximum(g, b)
    is_red_eye = (r > 100) & (r > other_max * 1.5)
    if not is_red_eye.any():
        return arr
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    out_rgb = rgb.copy()
    # Replace the red channel with the luma average, weighted by intensity.
    blended_r = r * (1.0 - intensity) + luma * intensity
    out_rgb[..., 0] = np.where(is_red_eye, blended_r, r)
    out = arr.copy()
    out[..., :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Eye sharpening
# ---------------------------------------------------------------------------


def sharpen_region(arr: np.ndarray, intensity: float, radius: int = 2) -> np.ndarray:
    """Unsharp mask: sharpened = arr + intensity * (arr - blur(arr))."""
    _validate_rgba(arr)
    intensity = _clamp(intensity, INTENSITY_MIN, INTENSITY_MAX) * 2.0
    if intensity <= 0.0:
        return arr
    rgb = arr[..., :3].astype(np.float32)
    blurred = _box_blur_rgb(arr[..., :3], radius).astype(np.float32)
    sharpened = rgb + intensity * (rgb - blurred)
    out = arr.copy()
    out[..., :3] = np.clip(sharpened, 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_rgba(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"portrait retouch expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _box_blur_rgb(rgb: np.ndarray, radius: int) -> np.ndarray:
    """Reuses the deflicker / portrait-blur cumsum trick."""
    blurred = np.empty_like(rgb)
    for channel in range(3):
        blurred[..., channel] = _box_blur_plane(rgb[..., channel], radius)
    return blurred


def _box_blur_plane(plane: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return plane.copy()
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
    return np.clip(blurred / (kernel * kernel) + 0.5, 0, 255).astype(np.uint8)
