"""Auto color correction — three one-click tonal / colour fixes.

The most-used "AI button" trio every paint app provides:

* :func:`auto_levels` — per-channel min/max stretch. Each of R, G,
  B is stretched independently so the darkest pixel of every
  channel becomes 0 and the brightest becomes 255. Lifts shadows
  and recovers highlights, but can introduce a colour cast if the
  channels' tonal ranges differ.
* :func:`auto_contrast` — luminance-based stretch. Computes the
  image's luminance min and max, then scales every channel
  uniformly so the luminance range expands to 0..255. Preserves
  colour balance unlike auto_levels — useful on photos where the
  colour temperature should stay intact.
* :func:`auto_color` — per-channel mean → mid-grey. Removes a
  colour cast by shifting each channel so its mean lands at 128
  (the assumption: a "naturally lit" scene has roughly equal R, G,
  B means in aggregate).

All three preserve the alpha channel and never mutate the input.
Pure numpy, no scipy dependency.
"""
from __future__ import annotations

import numpy as np


def auto_levels(image: np.ndarray) -> np.ndarray:
    """Per-channel min/max stretch to full ``[0, 255]`` range."""
    _check_rgba(image)
    out = image.copy()
    for ch in range(3):
        chan = image[..., ch]
        cmin = int(chan.min())
        cmax = int(chan.max())
        if cmax <= cmin:
            continue
        stretched = (chan.astype(np.float32) - cmin) / float(cmax - cmin) * 255.0
        out[..., ch] = np.clip(stretched, 0.0, 255.0).astype(np.uint8)
    return out


def auto_contrast(image: np.ndarray) -> np.ndarray:
    """Luminance-based stretch — preserves colour balance, only
    expands tonal range."""
    _check_rgba(image)
    rgb = image[..., :3].astype(np.float32)
    luminance = (
        0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    )
    lmin = float(luminance.min())
    lmax = float(luminance.max())
    out = image.copy()
    if lmax <= lmin:
        return out
    scale = 255.0 / (lmax - lmin)
    for ch in range(3):
        stretched = (rgb[..., ch] - lmin) * scale
        out[..., ch] = np.clip(stretched, 0.0, 255.0).astype(np.uint8)
    return out


def auto_color(image: np.ndarray) -> np.ndarray:
    """Per-channel mean shift toward mid-grey — removes colour cast."""
    _check_rgba(image)
    out = image.copy()
    for ch in range(3):
        chan = image[..., ch].astype(np.float32)
        mean = float(chan.mean())
        shifted = chan + (128.0 - mean)
        out[..., ch] = np.clip(shifted, 0.0, 255.0).astype(np.uint8)
    return out


def _check_rgba(image: np.ndarray) -> None:
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
