"""Per-channel image statistics and histogram CSV export.

Quantitative read-outs for inspection: mean / min / max / std / median per RGB
channel plus luminance, and a CSV dump of the 256-bin per-channel histogram for
analysis in a spreadsheet. Pure NumPy + stdlib, building on the histogram
binning in :mod:`Imervue.image.histogram`.
"""
from __future__ import annotations

import csv
import io

import numpy as np

from Imervue.image.histogram import compute_histogram
from Imervue.image.sharpness import to_luma

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_CHANNEL_NAMES = ("r", "g", "b", "luma")


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape}")


def _channel_stats(plane: np.ndarray) -> dict[str, float]:
    flat = plane.astype(np.float64)
    return {
        "mean": float(flat.mean()),
        "min": float(flat.min()),
        "max": float(flat.max()),
        "std": float(flat.std()),
        "median": float(np.median(flat)),
    }


def image_statistics(arr: np.ndarray) -> dict[str, dict[str, float]]:
    """Return per-channel (r, g, b, luma) mean/min/max/std/median for *arr*."""
    _validate(arr)
    rgb = arr[..., :3]
    stats = {name: _channel_stats(rgb[..., i]) for i, name in enumerate(("r", "g", "b"))}
    stats["luma"] = _channel_stats(to_luma(arr))
    return stats


def histogram_csv(arr: np.ndarray) -> str:
    """Return a CSV string with columns ``value,r,g,b,luma`` over 256 levels."""
    _validate(arr)
    hist = compute_histogram(arr)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["value", *_CHANNEL_NAMES])
    for value in range(256):
        writer.writerow([
            value,
            int(hist.r[value]), int(hist.g[value]),
            int(hist.b[value]), int(hist.luma[value]),
        ])
    return buffer.getvalue()
