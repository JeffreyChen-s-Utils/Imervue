"""EXIF orientation — bake the camera's rotation flag into the pixels.

Cameras and phones record how the device was held in EXIF tag 0x0112 rather
than rotating the pixels, so a viewer that ignores it shows portrait shots
sideways. This module maps the eight orientation codes to the matching
flip/rotate and applies it, so the saved pixels are upright everywhere.

Pure NumPy transforms (unit-tested); the EXIF read is a thin Pillow wrapper.
"""
from __future__ import annotations

import re

import numpy as np
from PIL import Image

from Imervue.image.read_errors import IMAGE_READ_ERRORS

_TOP_LEFT = 1  # the "already upright" orientation
_ORIENTATION_TAG = 0x0112

QUARTER_TURN_CODES: frozenset[int] = frozenset({5, 6, 7, 8})
"""Orientations that turn the image a quarter turn, so its upright width and height swap."""

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


# Code → Pillow transpose; the same mapping ``ImageOps.exif_transpose`` uses.
_PIL_TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def exif_orientation(img: Image.Image) -> int:
    """Return the EXIF orientation code of an open image (1 when absent or unreadable)."""
    try:
        return int(img.getexif().get(_ORIENTATION_TAG, _TOP_LEFT))
    except (*IMAGE_READ_ERRORS, AttributeError, TypeError):   # corrupt EXIF, or a non-numeric tag
        return _TOP_LEFT


def transpose_for(img: Image.Image, code: int) -> Image.Image:
    """Return *img* turned upright for orientation *code*; *img* itself when no turn is needed.

    Unlike ``ImageOps.exif_transpose`` this never copies an already-upright
    image, which matters for a full-resolution load. Like it, the result no
    longer carries the orientation tag (``transpose`` copies ``info``), so a
    later reader can't turn the pixels a second time.
    """
    method = _PIL_TRANSPOSE.get(code)
    if method is None:
        return img
    turned = img.transpose(method)
    _drop_orientation_tag(turned)
    return turned


# XMP spellings of the orientation Pillow's ``getexif`` also reads.
_XMP_ORIENTATION = (r'tiff:Orientation="[0-9]"', r"<tiff:Orientation>[0-9]</tiff:Orientation>")


def _drop_orientation_tag(img: Image.Image) -> None:
    """Remove the EXIF and XMP orientation from *img*'s ``info``, in place."""
    try:
        exif = img.getexif()
    except IMAGE_READ_ERRORS:   # unreadable EXIF: drop it rather than risk a second turn
        img.info.pop("exif", None)
        return
    if _ORIENTATION_TAG not in exif:
        return
    del exif[_ORIENTATION_TAG]
    if "exif" in img.info:
        img.info["exif"] = exif.tobytes()
    for key in ("XML:com.adobe.xmp", "xmp"):
        if key in img.info:
            img.info[key] = _strip_xmp_orientation(img.info[key])


def _strip_xmp_orientation(value):
    """Return *value* (str, bytes or a tuple of bytes) without its orientation attribute."""
    if isinstance(value, tuple):
        return tuple(_strip_xmp_orientation(part) for part in value)
    for pattern in _XMP_ORIENTATION:
        if isinstance(value, str):
            value = re.sub(pattern, "", value)
        else:
            value = re.sub(pattern.encode(), b"", value)
    return value


def upright(img: Image.Image) -> Image.Image:
    """Return *img* turned upright by its own EXIF orientation."""
    return transpose_for(img, exif_orientation(img))


def read_orientation(path: str) -> int:
    """Return the EXIF orientation code of *path* (1 when absent / unreadable)."""
    try:
        with Image.open(path) as img:
            return exif_orientation(img)
    except IMAGE_READ_ERRORS:
        return _TOP_LEFT


def oriented_array(path: str) -> np.ndarray:
    """Load *path* as RGBA and apply its EXIF orientation."""
    with Image.open(path) as img:
        rgba = np.array(img.convert("RGBA"))
    return transform_for_orientation(rgba, read_orientation(path))
