"""Pixel dimensions of an image file, read from its header without decoding it.

Camera RAW goes through libraw; Pillow would report the embedded preview's
size. HEIC and JPEG XL get their Pillow codec registered first.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from Imervue.image.formats import RAW_EXTENSIONS, ensure_pillow_opener
from Imervue.image.raw_loader import raw_dimensions
from Imervue.image.read_errors import IMAGE_READ_ERRORS


def image_dimensions(path: str | Path) -> tuple[int, int] | None:
    """Return ``(width, height)`` of the image at *path*, or ``None`` when it can't be read."""
    ext = Path(path).suffix.lower()
    if ext in RAW_EXTENSIONS:
        return raw_dimensions(path)
    ensure_pillow_opener(ext)
    try:
        with Image.open(path) as img:
            return img.size
    except IMAGE_READ_ERRORS:
        return None
