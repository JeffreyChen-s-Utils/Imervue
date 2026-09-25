"""Pixel dimensions of an image file, read from its header without decoding it.

The size is the upright one the viewer shows: an EXIF orientation that turns
the image a quarter turn swaps the sides. Camera RAW goes through libraw;
Pillow would report the embedded preview's size. HEIC and JPEG XL get their
Pillow codec registered first. :func:`probe_image` adds the format and mode.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from Imervue.image.formats import RAW_EXTENSIONS, ensure_pillow_opener
from Imervue.image.orientation import QUARTER_TURN_CODES, exif_orientation
from Imervue.image.raw_loader import raw_dimensions
from Imervue.image.read_errors import IMAGE_READ_ERRORS


def probe_image(path: str | Path) -> tuple[str, str, int, int]:
    """Return ``(format, mode, width, height)`` of *path* from its header.

    Raises ``IMAGE_READ_ERRORS`` for a file that can't be read. A camera RAW
    reports its extension as the format (``"CR3"``), ``"RGB"`` and the size
    libraw develops; anything else Pillow's format and mode.
    """
    ext = Path(path).suffix.lower()
    if ext in RAW_EXTENSIONS:
        size = raw_dimensions(path)
        if size is None:
            raise OSError(f"libraw can't read {path}")
        return ext.lstrip(".").upper(), "RGB", *size
    ensure_pillow_opener(ext)
    with Image.open(path) as img:
        width, height = img.size
        if exif_orientation(img) in QUARTER_TURN_CODES:
            width, height = height, width
        return img.format or "", img.mode, width, height


def image_dimensions(path: str | Path) -> tuple[int, int] | None:
    """Return the upright ``(width, height)`` of the image at *path*, or ``None`` if unreadable."""
    try:
        _format, _mode, width, height = probe_image(path)
    except IMAGE_READ_ERRORS:
        return None
    return width, height
