"""Kaleidoscope — mirror one angular wedge around the centre.

GIMP's *Kaleidoscope*: pick a wedge of ``360 / segments`` degrees and reflect it
repeatedly around the image centre, so the whole frame becomes an n-fold
symmetric pattern built from that single slice. Implemented as a reverse map —
each output pixel's angle is folded back into the base wedge, then the source is
sampled there.

Pure NumPy on ``HxWx3/4`` uint8 — ships in the main program. Returns RGBA.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.resample import (
    RGB_CHANNELS as _RGB_CHANNELS,
    RGBA_CHANNELS as _RGBA_CHANNELS,
    ensure_rgba,
    sample_bilinear,
)

_TWO_PI = 2.0 * np.pi
_MIN_SEGMENTS = 2


def fold_angle(theta: np.ndarray, segments: int, angle_offset: float) -> np.ndarray:
    """Fold angles *theta* into the base wedge, mirroring within each segment.

    Angles are taken modulo the segment width and reflected about the segment's
    half-line, giving the alternating mirror symmetry of a real kaleidoscope.
    """
    seg = _TWO_PI / segments
    local = np.mod(theta - angle_offset, seg)
    folded = np.where(local > seg / 2.0, seg - local, local)
    return folded + angle_offset


def kaleidoscope(
    arr: np.ndarray,
    segments: int = 6,
    center: tuple[float, float] | None = None,
    angle_offset: float = 0.0,
) -> np.ndarray:
    """Return *arr* mirrored into *segments* kaleidoscope wedges.

    *center* is the ``(x, y)`` pivot (image centre when omitted); *angle_offset*
    rotates the wedge. *segments* must be at least two.
    """
    _validate(arr, segments)
    rgba = ensure_rgba(arr)
    height, width = rgba.shape[:2]
    cx, cy = center if center is not None else ((width - 1) / 2.0, (height - 1) / 2.0)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    dx, dy = xx - cx, yy - cy
    radius = np.hypot(dx, dy)
    sample_angle = fold_angle(np.arctan2(dy, dx), segments, angle_offset)
    return sample_bilinear(
        rgba, cx + radius * np.cos(sample_angle), cy + radius * np.sin(sample_angle),
    )


def _validate(arr: np.ndarray, segments: int) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
    if segments < _MIN_SEGMENTS:
        raise ValueError(f"segments must be >= {_MIN_SEGMENTS}, got {segments}")
