"""Histogram engine — pure-numpy bin counts for RGB / luminance.

A histogram dock plots how often each 0..255 value occurs across
the canvas. Used to spot clipped highlights / crushed blacks while
adjusting Curves / Levels.

The module owns the maths only — Qt rendering happens in
:mod:`Imervue.paint.histogram_dock`. Pure numpy so unit tests don't
need a display server.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

HISTOGRAM_BINS = 256


@dataclass(frozen=True)
class Histogram:
    """Per-channel bin counts.

    All four arrays are length 256 ``int64``. ``luma`` uses the
    Rec. 709 coefficients used elsewhere in Imervue so the value
    here matches what the Curves filter operates on.
    """

    r: np.ndarray
    g: np.ndarray
    b: np.ndarray
    luma: np.ndarray

    def channel(self, name: str) -> np.ndarray:
        """Look up a channel by user-visible name (``'r'``, ``'g'``,
        ``'b'``, ``'luma'``).

        Raises ``ValueError`` for unknown names so a careless dock
        edit fails loudly rather than silently picking the wrong
        channel.
        """
        if name not in self.channels():
            raise ValueError(
                f"unknown channel {name!r}; expected one of {self.channels()}",
            )
        return getattr(self, name)

    @staticmethod
    def channels() -> tuple[str, str, str, str]:
        return ("r", "g", "b", "luma")


def compute_histogram(image: np.ndarray) -> Histogram:
    """Compute RGB + luma histograms for an HxWx4 ``uint8`` RGBA image.

    Pixels with alpha 0 are treated like any other pixel — they
    still contribute to the bin counts. (A future refinement could
    exclude transparent pixels, but the convention in Photoshop /
    MediBang is to count them too.)
    """
    if (
        image.ndim != 3
        or image.shape[2] != 4
        or image.dtype != np.uint8
    ):
        raise ValueError(
            f"compute_histogram expects HxWx4 uint8 RGBA, got {image.shape}"
            f" {image.dtype}",
        )
    flat = image.reshape(-1, 4)
    r = np.bincount(flat[:, 0], minlength=HISTOGRAM_BINS).astype(np.int64)
    g = np.bincount(flat[:, 1], minlength=HISTOGRAM_BINS).astype(np.int64)
    b = np.bincount(flat[:, 2], minlength=HISTOGRAM_BINS).astype(np.int64)
    # Rec. 709 luminance — match the Curves / luminance filter.
    luma_float = (
        0.2126 * flat[:, 0].astype(np.float32)
        + 0.7152 * flat[:, 1].astype(np.float32)
        + 0.0722 * flat[:, 2].astype(np.float32)
    )
    luma_uint = np.clip(luma_float + 0.5, 0, 255).astype(np.uint8)
    luma = np.bincount(luma_uint, minlength=HISTOGRAM_BINS).astype(np.int64)
    return Histogram(r=r, g=g, b=b, luma=luma)


def empty_histogram() -> Histogram:
    """Return a histogram with all-zero bin counts.

    Used by the dock when there's no document loaded so the rendering
    code path always has a valid Histogram to draw against.
    """
    zeros = np.zeros(HISTOGRAM_BINS, dtype=np.int64)
    return Histogram(r=zeros.copy(), g=zeros.copy(),
                     b=zeros.copy(), luma=zeros.copy())


def normalise(channel: np.ndarray) -> np.ndarray:
    """Divide a bin-count array by its peak so the dock can plot
    everything in [0, 1] regardless of canvas size.

    All-zero input returns all-zero output (no division-by-zero).
    """
    if channel.ndim != 1:
        raise ValueError(
            f"channel must be 1-D, got shape {channel.shape}",
        )
    peak = float(channel.max())
    if peak <= 0:
        return np.zeros_like(channel, dtype=np.float32)
    return (channel.astype(np.float32) / peak).astype(np.float32)


def merge_histograms(hists: Iterable[Histogram]) -> Histogram:
    """Sum a sequence of histograms bin-by-bin — useful for compositing
    a multi-tab workspace's stats into one display."""
    items = list(hists)
    if not items:
        return empty_histogram()
    r = np.zeros(HISTOGRAM_BINS, dtype=np.int64)
    g = np.zeros(HISTOGRAM_BINS, dtype=np.int64)
    b = np.zeros(HISTOGRAM_BINS, dtype=np.int64)
    luma = np.zeros(HISTOGRAM_BINS, dtype=np.int64)
    for h in items:
        r += h.r
        g += h.g
        b += h.b
        luma += h.luma
    return Histogram(r=r, g=g, b=b, luma=luma)
