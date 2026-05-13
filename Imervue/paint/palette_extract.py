"""Palette extraction — median-cut quantisation on an RGBA layer.

raster paint apps's "color theme from image" workflow. Given the active layer
(or composite), produce a small ordered palette that spans the
image's colour range. The classic algorithm is *median cut*:

1. Treat every opaque pixel as a point in 3-D RGB space.
2. Find the colour-axis range of the bucket and split it through the
   median along the longest axis.
3. Repeat on every bucket until the desired number of buckets exists.
4. Each final bucket's mean colour is one palette entry.

Median cut beats naive histogram-by-quantization because it adapts
to the image: a near-monochrome painting yields buckets that
discriminate fine tonal differences instead of all collapsing into
one quantization bin.

Pure-numpy / Qt-free so the swatch panel can call it from anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PALETTE_MIN = 1
PALETTE_MAX = 64
DEFAULT_PALETTE_SIZE = 8

# Pixels with alpha at or below this are ignored — they don't
# represent a colour the user painted with.
DEFAULT_ALPHA_THRESHOLD = 32


@dataclass(frozen=True)
class PaletteEntry:
    """One extracted colour plus the pixel count it represents."""

    color: tuple[int, int, int]
    pixel_count: int


def extract_palette(
    image: np.ndarray,
    *,
    n_colors: int = DEFAULT_PALETTE_SIZE,
    alpha_threshold: int = DEFAULT_ALPHA_THRESHOLD,
) -> list[PaletteEntry]:
    """Return up to ``n_colors`` representative colours of ``image``.

    The output is sorted by ``pixel_count`` descending so the
    dominant colour is entry 0 — convenient for swatch-panel UIs
    that show "main" colours first. Empty / fully-transparent input
    returns an empty list.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got shape={image.shape}"
            f" dtype={image.dtype}",
        )
    if not PALETTE_MIN <= int(n_colors) <= PALETTE_MAX:
        raise ValueError(
            f"n_colors must be in [{PALETTE_MIN}, {PALETTE_MAX}],"
            f" got {n_colors}",
        )
    if not 0 <= int(alpha_threshold) <= 255:
        raise ValueError(
            f"alpha_threshold must be in [0, 255], got {alpha_threshold}",
        )

    rgb = image[..., :3]
    alpha = image[..., 3]
    opaque = alpha > int(alpha_threshold)
    if not opaque.any():
        return []
    pixels = rgb[opaque].reshape(-1, 3).astype(np.int32)
    if pixels.size == 0:
        return []
    buckets = _median_cut(pixels, int(n_colors))
    entries = [
        PaletteEntry(
            color=(
                int(round(bucket.mean(axis=0)[0])),
                int(round(bucket.mean(axis=0)[1])),
                int(round(bucket.mean(axis=0)[2])),
            ),
            pixel_count=int(bucket.shape[0]),
        )
        for bucket in buckets
    ]
    entries.sort(key=lambda e: e.pixel_count, reverse=True)
    return entries[:int(n_colors)]


def inject_palette_into_state(state, palette: list[PaletteEntry]) -> int:
    """Push the palette colours into ``state.color_history``.

    Replaces the existing history with the extracted palette in
    dominant-first order. Returns the count of colours actually
    injected (capped at :data:`Imervue.paint.tool_state.COLOR_HISTORY_MAX`).
    """
    from Imervue.paint.tool_state import COLOR_HISTORY_MAX, EVENT_HISTORY

    truncated = palette[:COLOR_HISTORY_MAX]
    state.color_history.clear()
    state.color_history.extend(entry.color for entry in truncated)
    state._emit(EVENT_HISTORY)  # noqa: SLF001
    return len(truncated)


def _median_cut(pixels: np.ndarray, n_buckets: int) -> list[np.ndarray]:
    """Split ``pixels`` (Nx3 int32) into ``n_buckets`` median-cut groups.

    Iteratively picks the bucket with the widest channel range and
    partitions it along that channel's median. Stops early when
    every remaining bucket has ≤ 1 unique pixel — splitting wouldn't
    yield distinct colours.
    """
    if n_buckets <= 1 or pixels.shape[0] == 0:
        return [pixels]
    buckets: list[np.ndarray] = [pixels]
    while len(buckets) < n_buckets:
        target = _pick_widest_bucket(buckets)
        if target is None:
            break
        index, axis, _span = target
        if not _split_bucket_in_place(buckets, index, axis):
            break
    return buckets


def _pick_widest_bucket(
    buckets: list[np.ndarray],
) -> tuple[int, int, int] | None:
    """Return ``(index, axis, span)`` of the bucket with the widest
    channel range, or ``None`` when every remaining bucket is too
    small / too narrow to split further."""
    widest_index = -1
    widest_range = -1
    widest_axis = 0
    for i, bucket in enumerate(buckets):
        if bucket.shape[0] < 2:
            continue
        ranges = bucket.max(axis=0) - bucket.min(axis=0)
        axis = int(np.argmax(ranges))
        span = int(ranges[axis])
        if span > widest_range:
            widest_index = i
            widest_range = span
            widest_axis = axis
    if widest_index < 0 or widest_range == 0:
        return None
    return (widest_index, widest_axis, widest_range)


def _split_bucket_in_place(
    buckets: list[np.ndarray], index: int, axis: int,
) -> bool:
    """Median-split ``buckets[index]`` along ``axis``. Returns ``True``
    when the split produced two non-empty halves."""
    bucket = buckets[index]
    sorted_bucket = bucket[bucket[:, axis].argsort()]
    midpoint = sorted_bucket.shape[0] // 2
    if midpoint == 0 or midpoint == sorted_bucket.shape[0]:
        return False
    buckets[index] = sorted_bucket[:midpoint]
    buckets.append(sorted_bucket[midpoint:])
    return True
