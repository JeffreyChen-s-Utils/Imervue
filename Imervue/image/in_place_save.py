"""Which files can be edited and written back over themselves, and in which format.

Pillow opens more than it can faithfully write back. It reads a camera RAW
(CR2 / NEF / DNG …) as its small embedded TIFF preview, and an animated GIF /
WebP / APNG or a multi-page TIFF as its first frame. Saving the edited pixels
back over such a file destroys it: a 9 MB CR2 became a 0.8 MB preview-sized
TIFF. Every in-place writer (rotate, Modify's apply-crop, the annotation
editor's Save) asks :func:`can_rewrite_in_place` first.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from Imervue.image.read_errors import IMAGE_READ_ERRORS

_IN_PLACE_FORMATS: dict[str, str] = {
    ".png": "PNG",
    ".jpg": "JPEG", ".jpeg": "JPEG", ".jpe": "JPEG", ".jfif": "JPEG",
    ".bmp": "BMP",
    ".tif": "TIFF", ".tiff": "TIFF",
    ".webp": "WEBP",
    ".gif": "GIF",
}


def in_place_format(path: str | Path) -> str | None:
    """Return the Pillow format to write *path* back in, or ``None`` if it can't be."""
    return _IN_PLACE_FORMATS.get(Path(path).suffix.lower())


def can_rewrite_in_place(path: str | Path) -> bool:
    """Whether decoding *path*, editing the pixels and saving it back keeps the file whole.

    False for formats Pillow cannot write back faithfully (camera RAW, HEIC,
    JPEG XL, SVG, video), for multi-frame files (animated GIF / WebP / APNG,
    multi-page TIFF, MPO), whose other frames a single-image save would drop,
    and for a file that can't be read at all.
    """
    if in_place_format(path) is None:
        return False
    try:
        with Image.open(path) as img:
            return getattr(img, "n_frames", 1) == 1
    except IMAGE_READ_ERRORS:
        return False
