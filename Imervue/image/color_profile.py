"""Convert images that embed a colour profile to sRGB, the space the screen shows.

Phones save Display P3 and many cameras Adobe RGB, with the profile embedded.
Read as plain numbers those pixels look dull; a CMYK JPEG's naive conversion
is simply wrong. Converting through the embedded profile (littleCMS, via
Pillow's ``ImageCms``) gives the colours the file describes.

An image without a profile, or with an sRGB one, is returned untouched, so the
common case costs nothing beyond reading ``info``.
"""
from __future__ import annotations

import io
import logging
from functools import lru_cache

from PIL import Image, ImageCms

logger = logging.getLogger("Imervue.color_profile")

# Input mode -> the mode the converted image has. Everything else is left alone.
_OUTPUT_MODE = {"RGB": "RGB", "RGBA": "RGBA", "CMYK": "RGB"}


@lru_cache(maxsize=32)
def _transform(icc: bytes, mode: str) -> ImageCms.ImageCmsTransform | None:
    """Build (once per profile and mode) the transform to sRGB; ``None`` when not needed."""
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        if "srgb" in ImageCms.getProfileDescription(source).lower():
            return None
        return ImageCms.buildTransform(
            source, ImageCms.createProfile("sRGB"), mode, _OUTPUT_MODE[mode],
        )
    except (ImageCms.PyCMSError, OSError, ValueError):
        logger.debug("Unusable embedded colour profile; showing the pixels as stored",
                     exc_info=True)
        return None


def to_srgb(img: Image.Image) -> Image.Image:
    """Return *img* converted from its embedded ICC profile to sRGB, or *img* itself.

    The result carries no ``icc_profile``: its pixels are sRGB now, and a
    later reader must not convert them again. A CMYK image comes back RGB.
    """
    icc = img.info.get("icc_profile")
    if not icc or img.mode not in _OUTPUT_MODE:
        return img
    transform = _transform(bytes(icc), img.mode)
    if transform is None:
        return img
    converted = ImageCms.applyTransform(img, transform)
    converted.info.pop("icc_profile", None)
    return converted
