"""Polar coordinate warp — wrap an image into a disc or unroll it.

GIMP's *Polar Coordinates* and Paint.NET's *Polar Inversion*: either bend a
rectangular image around a circle (the "tiny planet" / circular-panorama look)
or unroll a disc back into a strip. Both directions are a reverse map sampled
bilinearly through the shared resampler.

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


def polar_distort(arr: np.ndarray, to_polar: bool = True, invert: bool = False) -> np.ndarray:
    """Warp *arr* between rectangular and polar coordinates.

    When *to_polar* is True the image is wrapped into a disc (rows become rings,
    columns become angles); when False a disc is unrolled back into a strip.
    *invert* flips the radial direction, swapping which edge maps to the centre.
    """
    _validate(arr)
    rgba = ensure_rgba(arr)
    height, width = rgba.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
    max_radius = max(1.0, min(cx, cy))
    if to_polar:
        sx, sy = _to_polar_coords(xx, yy, cx, cy, max_radius, width, height, invert)
    else:
        sx, sy = _from_polar_coords(xx, yy, cx, cy, max_radius, width, height, invert)
    return sample_bilinear(rgba, sx, sy)


def _to_polar_coords(xx, yy, cx, cy, max_radius, width, height, invert):
    """Disc output -> rectangular source: angle picks the column, radius the row."""
    angle = np.arctan2(yy - cy, xx - cx)
    radius = np.hypot(xx - cx, yy - cy) / max_radius
    src_x = (angle + np.pi) / _TWO_PI * (width - 1)
    radial = 1.0 - radius if invert else radius
    return src_x, radial * (height - 1)


def _from_polar_coords(xx, yy, cx, cy, max_radius, width, height, invert):
    """Rectangular output -> disc source: column is the angle, row the radius."""
    angle = xx / (width - 1) * _TWO_PI - np.pi
    radial = yy / (height - 1)
    radial = 1.0 - radial if invert else radial
    radius = radial * max_radius
    return cx + radius * np.cos(angle), cy + radius * np.sin(angle)


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
