"""Pure-numpy histogram and exposure-clipping statistics for the viewer.

The deep-zoom overlay draws a live histogram and an over/under-exposure
warning. The binning and clipping math live here, extracted from the QPainter
overlay so they are unit-testable without a GL context — the overlay just
caches a :class:`Histogram` / :class:`ClipStats` per image and renders them.

Clipping convention (matches what photographers expect from a "blinkies" /
histogram-triangle warning):

* **over** — a pixel counts as a blown highlight when *any* channel is at or
  above ``high`` (a single saturated channel already loses detail).
* **under** — a pixel counts as a crushed shadow only when *all* channels are
  at or below ``low`` (true, detail-less black).

``high`` / ``low`` default one step in from the hard 0 / 255 so pixels that are
visually clipped but land on 254 / 1 after tone mapping still warn.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Rec. 601 luma weights — the perceptual grey the eye reads from RGB.
_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float64)
DEFAULT_HIGH = 254
DEFAULT_LOW = 1
BIN_COUNT = 256
_HIST_RANGE = (0, 256)


@dataclass(frozen=True)
class Histogram:
    """Per-channel 256-bin counts plus a perceptual-luma channel."""

    r: np.ndarray
    g: np.ndarray
    b: np.ndarray
    luma: np.ndarray


@dataclass(frozen=True)
class ClipStats:
    """Share of pixels clipped at each end of the exposure range, in ``[0, 1]``."""

    over_fraction: float
    under_fraction: float


def _rgb_view(img: np.ndarray) -> np.ndarray:
    """Validate and return the RGB channels (alpha dropped) of an 8-bit image."""
    if img.ndim != 3 or img.shape[2] not in (3, 4) or img.dtype != np.uint8:
        raise ValueError(
            f"expected HxWx3/4 uint8 image, got {img.shape} {img.dtype}",
        )
    return img[:, :, :3]


def _luma(rgb: np.ndarray) -> np.ndarray:
    """Rec. 601 luma as a uint8 HxW array."""
    flat = rgb.reshape(-1, 3).astype(np.float64)
    luma = flat @ _LUMA_WEIGHTS
    return np.clip(np.rint(luma), 0, 255).astype(np.uint8)


def compute_histogram(img: np.ndarray) -> Histogram:
    """Return the R / G / B / luma histograms (256 bins each) of *img*.

    *img* is HxWx3 or HxWx4 uint8; alpha is ignored. Each channel's counts sum
    to the pixel total, so callers can derive percentages directly.
    """
    rgb = _rgb_view(img)
    r = np.histogram(rgb[:, :, 0], bins=BIN_COUNT, range=_HIST_RANGE)[0]
    g = np.histogram(rgb[:, :, 1], bins=BIN_COUNT, range=_HIST_RANGE)[0]
    b = np.histogram(rgb[:, :, 2], bins=BIN_COUNT, range=_HIST_RANGE)[0]
    luma = np.histogram(_luma(rgb), bins=BIN_COUNT, range=_HIST_RANGE)[0]
    return Histogram(r=r, g=g, b=b, luma=luma)


def compute_clipping(
    img: np.ndarray,
    *,
    high: int = DEFAULT_HIGH,
    low: int = DEFAULT_LOW,
) -> ClipStats:
    """Return the over/under-exposed pixel fractions of *img*.

    ``high`` / ``low`` are clamped into ``[0, 255]``; an empty image reports no
    clipping rather than dividing by zero.
    """
    rgb = _rgb_view(img)
    total = rgb.shape[0] * rgb.shape[1]
    if total == 0:
        return ClipStats(over_fraction=0.0, under_fraction=0.0)
    high = max(0, min(255, int(high)))
    low = max(0, min(255, int(low)))
    over = np.count_nonzero((rgb >= high).any(axis=-1))
    under = np.count_nonzero((rgb <= low).all(axis=-1))
    return ClipStats(
        over_fraction=over / total,
        under_fraction=under / total,
    )
