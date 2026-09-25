"""Pillow's settings for a desktop viewer, applied once by each entry point.

Pillow's defaults suit a server decoding uploads: it refuses giant pictures
and any file that ends early. On the desktop both kept real photos from
opening - a stitched panorama, and a file cut short by an interrupted
download or copy or recovered from a failing memory card, which a browser
still shows as far as it goes. Tests never run this, so they keep Pillow's
defaults.
"""
from __future__ import annotations

from PIL import ImageFile

from Imervue.system.pixel_limit import raise_pixel_limit


def configure_pillow() -> None:
    """Fit the pixel limit to this machine and read a file cut short as far as it goes.

    Process-wide: every later decode, in any thread, reads a truncated JPEG,
    PNG, TIFF, GIF or BMP instead of raising ``OSError`` - a baseline JPEG's
    missing rows grey, a PNG's black or transparent.
    """
    raise_pixel_limit()
    ImageFile.LOAD_TRUNCATED_IMAGES = True
