"""Pixel dimensions of an image file, read from its header without decoding it.

The size is the upright one the viewer shows: an EXIF orientation that turns
the image a quarter turn swaps the sides. Camera RAW goes through libraw;
Pillow would report the embedded preview's size. HEIC and JPEG XL get their
Pillow codec registered first.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from Imervue.image.formats import RAW_EXTENSIONS, ensure_pillow_opener
from Imervue.image.orientation import exif_orientation
from Imervue.image.raw_loader import raw_dimensions
from Imervue.image.read_errors import IMAGE_READ_ERRORS

# EXIF orientations that turn the image a quarter turn (transpose, rotate 90 / 270, transverse).
_QUARTER_TURNS = frozenset({5, 6, 7, 8})


def image_dimensions(path: str | Path) -> tuple[int, int] | None:
    """Return the upright ``(width, height)`` of the image at *path*, or ``None`` if unreadable."""
    ext = Path(path).suffix.lower()
    if ext in RAW_EXTENSIONS:
        return raw_dimensions(path)
    ensure_pillow_opener(ext)
    try:
        with Image.open(path) as img:
            width, height = img.size
            quarter_turn = exif_orientation(img) in _QUARTER_TURNS
    except IMAGE_READ_ERRORS:
        return None
    return (height, width) if quarter_turn else (width, height)
