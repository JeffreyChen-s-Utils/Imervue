"""Sample files for the "decode like the viewer" regression tests of the exporters."""
from __future__ import annotations

from PIL import Image

from _icc_profiles import DISPLAY_P3


def tagged_portrait(path, size=(40, 20)):
    """Stored *size* pixels tagged orientation 6: shown with its sides swapped."""
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", size, (90, 120, 150)).save(path, exif=exif)
    return path


def p3_green(path):
    """A pure Display P3 green, which lies outside sRGB: converted, it clips to (0, 255, …)."""
    Image.new("RGB", (8, 8), (0, 255, 0)).save(path, icc_profile=DISPLAY_P3)
    return path
