"""Emboss — directional-light relief from a luminance height field.

The classic GIMP/Krita *Emboss* filter: treat image luminance as a height map,
estimate each pixel's surface normal from the local gradient, and shade it
against a light coming from a chosen *azimuth* and *elevation*. Flat areas turn
a neutral mid-grey; edges catch a highlight on the lit side and a shadow on the
far side, giving a stamped-metal look. It also serves as the primitive a future
"Bevel & Emboss" layer style would build on.

Pure NumPy on ``HxWx3/4`` uint8 — ships in the main program. Alpha is preserved.
"""
from __future__ import annotations

import math

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_DEPTH_LIMIT = 10.0


def apply_emboss(
    arr: np.ndarray,
    azimuth_deg: float = 135.0,
    elevation_deg: float = 45.0,
    depth: float = 1.0,
    grayscale: bool = True,
) -> np.ndarray:
    """Return an embossed copy of *arr*.

    *azimuth_deg* is the in-plane light direction, *elevation_deg* its height
    above the surface (``0``–``90``), and *depth* (clamped to ``[0, 10]``)
    exaggerates the height field. When *grayscale* is True the result is a neutral
    relief; otherwise the original colours are modulated by the shading.
    """
    _validate(arr)
    rgb = arr[..., :3].astype(np.float32)
    height = (rgb @ _LUMA_WEIGHTS) / _MAX_8BIT
    shade = emboss_shade(height, azimuth_deg, elevation_deg, depth)
    if grayscale:
        out = np.repeat((shade * _MAX_8BIT)[..., None], _RGB_CHANNELS, axis=2)
    else:
        out = rgb * shade[..., None]
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return result


def emboss_shade(
    height: np.ndarray, azimuth_deg: float, elevation_deg: float, depth: float,
) -> np.ndarray:
    """Return the ``[0, 1]`` Lambert shading of a height field under a light.

    The surface normal at each pixel is ``(-dz/dx, -dz/dy, 1)`` scaled by
    *depth*; it is dotted with the unit light vector built from the azimuth and
    elevation, then clamped to ``[0, 1]``.
    """
    depth = float(np.clip(depth, 0.0, _DEPTH_LIMIT))
    grad_y, grad_x = np.gradient(height.astype(np.float32))
    nx = -grad_x * depth
    ny = -grad_y * depth
    nz = np.ones_like(height, dtype=np.float32)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    azimuth = math.radians(azimuth_deg)
    elevation = math.radians(elevation_deg)
    lx = math.cos(elevation) * math.cos(azimuth)
    ly = math.cos(elevation) * math.sin(azimuth)
    lz = math.sin(elevation)
    dot = (nx * lx + ny * ly + nz * lz) / norm
    return np.clip(dot, 0.0, 1.0)


def _validate(arr: np.ndarray) -> None:
    if (
        arr.ndim != _RGB_CHANNELS
        or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS)
        or arr.dtype != np.uint8
    ):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape} {arr.dtype}")
