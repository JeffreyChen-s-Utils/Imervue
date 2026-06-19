"""EXIF orientation — bake the camera's rotation flag into the pixels.

Cameras and phones record how the device was held in EXIF tag 0x0112 rather
than rotating the pixels, so a viewer that ignores it shows portrait shots
sideways. This module maps the eight orientation codes to the matching
flip/rotate and applies it, so the saved pixels are upright everywhere.

Pure NumPy transforms (unit-tested); the EXIF read is a thin Pillow wrapper.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

_TOP_LEFT = 1  # the "already upright" orientation
_ORIENTATION_TAG = 0x0112

# Code → array transform, matching PIL.ImageOps.exif_transpose semantics
# (np.rot90 is counter-clockwise; k=-1 is a clockwise quarter turn).
_TRANSFORMS = {
    1: lambda a: a,
    2: lambda a: a[:, ::-1],
    3: lambda a: a[::-1, ::-1],
    4: lambda a: a[::-1, :],
    5: lambda a: np.swapaxes(a, 0, 1),
    6: lambda a: np.rot90(a, -1),
    7: lambda a: np.swapaxes(a, 0, 1)[::-1, ::-1],
    8: lambda a: np.rot90(a, 1),
}


def transform_for_orientation(arr: np.ndarray, code: int) -> np.ndarray:
    """Return *arr* re-oriented for EXIF orientation *code* (1–8).

    Unknown codes fall back to the identity so a corrupt tag can never raise.
    """
    transform = _TRANSFORMS.get(int(code), _TRANSFORMS[_TOP_LEFT])
    return np.ascontiguousarray(transform(arr))


def read_orientation(path: str) -> int:
    """Return the EXIF orientation code of *path* (1 when absent / unreadable)."""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
        return int(exif.get(_ORIENTATION_TAG, _TOP_LEFT))
    except (OSError, ValueError, AttributeError):
        return _TOP_LEFT


def oriented_array(path: str) -> np.ndarray:
    """Load *path* as RGBA and apply its EXIF orientation."""
    with Image.open(path) as img:
        rgba = np.array(img.convert("RGBA"))
    return transform_for_orientation(rgba, read_orientation(path))
