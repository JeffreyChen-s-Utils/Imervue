"""
Lens correction — distortion, vignette, and chromatic aberration.

This module uses a lightweight pure-numpy model rather than a lensfun
database, so it works offline on any image without needing lens metadata.
Three knobs cover 80% of what a travelling photographer needs:

- **Distortion** — radial ``k1`` coefficient. Negative values pincushion
  the image (common on tele lenses); positive values barrel-distort
  (common on wide-angle zooms). Range ``[-0.5, +0.5]``.
- **Vignette** — amount of corner darkening to lift. Positive values
  brighten the corners (correcting vignette), negative values add a
  vignette. Range ``[-1.0, +1.0]``.
- **Chromatic aberration** — per-channel radial scale correction. Values
  near zero shift the red or blue channel slightly outward / inward so
  colour fringes on high-contrast edges line up. Range ``[-0.02, +0.02]``.

All three operations run on HxWx4 RGBA uint8 arrays and return a new
array of the same shape.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.lens_correction")

_EPS = 1e-6


@dataclass
class LensCorrectionOptions:
    """Simple lens correction parameters. All default to identity."""

    k1: float = 0.0              # radial distortion coefficient
    vignette: float = 0.0        # corner lift (-1..+1)
    ca_red: float = 0.0          # red-channel radial scale offset
    ca_blue: float = 0.0         # blue-channel radial scale offset

    def is_identity(self) -> bool:
        return (
            abs(self.k1) < _EPS
            and abs(self.vignette) < _EPS
            and abs(self.ca_red) < _EPS
            and abs(self.ca_blue) < _EPS
        )


def _undistort(arr: np.ndarray, k1: float) -> np.ndarray:
    """Apply radial distortion correction (pure numpy bilinear sample)."""
    if abs(k1) < _EPS:
        return arr
    h, w = arr.shape[:2]
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    ys, xs = np.indices((h, w), dtype=np.float32)
    dx = (xs - cx) / cx
    dy = (ys - cy) / cy
    r2 = dx * dx + dy * dy
    factor = 1.0 + k1 * r2
    src_x = cx + dx * cx * factor
    src_y = cy + dy * cy * factor
    return _bilinear_sample(arr, src_x, src_y)


def _bilinear_sample(arr: np.ndarray, src_x: np.ndarray, src_y: np.ndarray) -> np.ndarray:
    """Bilinear resample of ``arr`` at floating-point source coordinates."""
    h, w = arr.shape[:2]
    x0 = np.floor(src_x).astype(np.int32)
    y0 = np.floor(src_y).astype(np.int32)
    x1 = x0 + 1
    y1 = y0 + 1
    fx = src_x - x0
    fy = src_y - y0
    x0c = np.clip(x0, 0, w - 1)
    x1c = np.clip(x1, 0, w - 1)
    y0c = np.clip(y0, 0, h - 1)
    y1c = np.clip(y1, 0, h - 1)

    src = arr.astype(np.float32)
    p00 = src[y0c, x0c]
    p10 = src[y0c, x1c]
    p01 = src[y1c, x0c]
    p11 = src[y1c, x1c]
    top = p00 * (1 - fx)[..., None] + p10 * fx[..., None]
    bot = p01 * (1 - fx)[..., None] + p11 * fx[..., None]
    out = top * (1 - fy)[..., None] + bot * fy[..., None]
    return np.clip(out, 0.0, 255.0).astype(np.uint8)


def _devignette(arr: np.ndarray, amount: float) -> np.ndarray:
    """Radially brighten (amount>0) or darken (amount<0) toward the corners."""
    if abs(amount) < _EPS:
        return arr
    h, w = arr.shape[:2]
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    ys, xs = np.indices((h, w), dtype=np.float32)
    r2 = ((xs - cx) / cx) ** 2 + ((ys - cy) / cy) ** 2
    # gain = 1.0 at centre, 1.0 + amount at the corner (where r2 = 2).
    gain = 1.0 + amount * (r2 / 2.0)
    rgb = arr[..., :3].astype(np.float32) * gain[..., None]
    np.clip(rgb, 0.0, 255.0, out=rgb)
    out = arr.copy()
    out[..., :3] = rgb.astype(np.uint8)
    return out


def _correct_ca(arr: np.ndarray, red: float, blue: float) -> np.ndarray:
    """Per-channel radial scale correction for chromatic aberration."""
    if abs(red) < _EPS and abs(blue) < _EPS:
        return arr
    h, w = arr.shape[:2]
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    ys, xs = np.indices((h, w), dtype=np.float32)
    dx = xs - cx
    dy = ys - cy
    out = arr.copy()
    for channel, amount in ((0, red), (2, blue)):
        if abs(amount) < _EPS:
            continue
        scale = 1.0 + amount
        src_x = cx + dx * scale
        src_y = cy + dy * scale
        # Sample just the one channel (extend to 4 for the bilinear helper).
        mono = np.dstack([arr[..., channel]] * 4)
        resampled = _bilinear_sample(mono, src_x, src_y)
        out[..., channel] = resampled[..., 0]
    return out


def apply_lens_correction(
    arr: np.ndarray, options: LensCorrectionOptions,
) -> np.ndarray:
    """Pipeline: CA -> distortion -> vignette correction. Returns a new array."""
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("apply_lens_correction expects HxWx4 RGBA uint8")
    if options.is_identity():
        return arr
    arr = _correct_ca(arr, options.ca_red, options.ca_blue)
    arr = _undistort(arr, options.k1)
    arr = _devignette(arr, options.vignette)
    return arr
