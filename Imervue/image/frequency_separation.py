"""Frequency separation — split an image into low and high frequency layers.

The classic portrait-retouching workflow:

* The **low-frequency** layer holds the smooth colour and tone — this is
  what you blur out and then dodge-and-burn for skin work.
* The **high-frequency** layer holds the fine detail (pores, hair,
  texture) — encoded so that the detail can be recombined with any low-
  frequency edits via simple addition.

The split is performed with a Gaussian blur of configurable radius. The
high-frequency layer is centred at neutral grey (128) so additive
recombination with the blurred low-frequency yields back the original.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.frequency_separation")

RADIUS_MIN = 1
RADIUS_MAX = 64
NEUTRAL_GREY = 128


@dataclass(frozen=True)
class FrequencySeparationResult:
    """Pair of (low_freq, high_freq) layers, both HxWx4 uint8 RGBA."""

    low_frequency: np.ndarray
    high_frequency: np.ndarray


def separate_frequencies(
    arr: np.ndarray,
    radius: int = 8,
) -> FrequencySeparationResult:
    """Split ``arr`` into low/high frequency layers.

    The low layer is a Gaussian blur of the input. The high layer is the
    per-pixel difference centred at ``NEUTRAL_GREY`` so a destination
    application that adds ``low + (high - 128)`` recovers the original.
    """
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"separate_frequencies expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    radius = max(RADIUS_MIN, min(RADIUS_MAX, int(radius)))

    low_rgb = _gaussian_blur(arr[..., :3], radius)
    diff = arr[..., :3].astype(np.int16) - low_rgb.astype(np.int16)
    high_rgb = np.clip(diff + NEUTRAL_GREY, 0, 255).astype(np.uint8)

    low = arr.copy()
    low[..., :3] = low_rgb
    high = arr.copy()
    high[..., :3] = high_rgb
    return FrequencySeparationResult(low_frequency=low, high_frequency=high)


def recombine_frequencies(
    low: np.ndarray,
    high: np.ndarray,
) -> np.ndarray:
    """Inverse operation of :func:`separate_frequencies`.

    Returns ``low + (high - 128)`` clamped to the uint8 range. Useful in
    tests to verify the round-trip is loss-bounded, and for users who
    edited the layers separately and want to merge back in-app.
    """
    if low.shape != high.shape or low.dtype != np.uint8 or high.dtype != np.uint8:
        raise ValueError("recombine_frequencies expects matching HxWx4 uint8 RGBA")
    rgb = (
        low[..., :3].astype(np.int16)
        + high[..., :3].astype(np.int16)
        - NEUTRAL_GREY
    )
    out = low.copy()
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out


def _gaussian_blur(rgb: np.ndarray, radius: int) -> np.ndarray:
    """Separable Gaussian blur on each channel.

    A pure-numpy convolution avoids pulling OpenCV into this module's
    dependency surface — frequency separation is a niche tool, and the
    one-time cost of a small kernel matrix multiply per channel is fine.
    """
    kernel = _gaussian_kernel_1d(radius)
    blurred = np.empty_like(rgb)
    for channel in range(3):
        plane = rgb[..., channel].astype(np.float32)
        plane = _convolve_axis(plane, kernel, axis=0)
        plane = _convolve_axis(plane, kernel, axis=1)
        blurred[..., channel] = np.clip(plane + 0.5, 0, 255).astype(np.uint8)
    return blurred


def _gaussian_kernel_1d(radius: int) -> np.ndarray:
    """Symmetric 1-D Gaussian kernel with sigma = radius / 2."""
    sigma = max(1.0, radius / 2.0)
    half = max(1, int(round(sigma * 3)))
    indices = np.arange(-half, half + 1, dtype=np.float32)
    kernel = np.exp(-(indices ** 2) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    return kernel


def _convolve_axis(plane: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    """Apply a 1-D kernel along ``axis`` with edge-replicating padding."""
    pad = kernel.size // 2
    pad_width = [(0, 0), (0, 0)]
    pad_width[axis] = (pad, pad)
    padded = np.pad(plane, pad_width, mode="edge")
    out = np.zeros_like(plane, dtype=np.float32)
    for i, weight in enumerate(kernel):
        slicer = [slice(None), slice(None)]
        slicer[axis] = slice(i, i + plane.shape[axis])
        out += padded[tuple(slicer)] * weight
    return out
