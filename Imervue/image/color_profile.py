"""Convert images that embed a colour profile to sRGB, the space the screen shows.

Phones save Display P3 and many cameras Adobe RGB, with the profile embedded.
Read as plain numbers those pixels look dull; a CMYK JPEG's naive conversion
is simply wrong. Converting through the embedded profile (littleCMS, via
Pillow's ``ImageCms``) gives the colours the file describes.

Greyscale files carry a grey profile: Photoshop's ``Dot Gain 20%`` or
``Gray Gamma 1.8``, whose midtones sRGB shows lighter or darker. A grey
profile maps every level to a neutral sRGB grey, so a grey image stays one
channel: its profile becomes a 256-entry curve applied to the levels.

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
_OUTPUT_MODE = {"RGB": "RGB", "RGBA": "RGBA", "CMYK": "RGB", "L": "RGB"}
# Converted level by level through _grey_curve, keeping one channel (and the alpha).
_GREY_MODES = ("L", "LA")
_LEVELS = 256


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


@lru_cache(maxsize=32)
def _grey_curve(icc: bytes) -> tuple[int, ...] | None:
    """The sRGB level each of a grey profile's 256 levels shows as; ``None`` when not needed."""
    transform = _transform(icc, "L")
    if transform is None:
        return None
    ramp = Image.frombytes("L", (_LEVELS, 1), bytes(range(_LEVELS)))
    return tuple(ImageCms.applyTransform(ramp, transform).getchannel("G").tobytes())


def _grey_to_srgb(img: Image.Image, icc: bytes) -> Image.Image:
    curve = _grey_curve(icc)
    if curve is None:
        return img
    alpha = list(range(_LEVELS)) if img.mode == "LA" else []
    return img.point(list(curve) + alpha)


def to_srgb(img: Image.Image) -> Image.Image:
    """Return *img* converted from its embedded ICC profile to sRGB, or *img* itself.

    The result carries no ``icc_profile``: its pixels are sRGB now, and a
    later reader must not convert them again. A CMYK image comes back RGB;
    a greyscale one stays greyscale.
    """
    icc = img.info.get("icc_profile")
    if not icc:
        return img
    if img.mode in _GREY_MODES:
        converted = _grey_to_srgb(img, bytes(icc))
    elif img.mode in _OUTPUT_MODE:
        transform = _transform(bytes(icc), img.mode)
        converted = img if transform is None else ImageCms.applyTransform(img, transform)
    else:
        return img
    if converted is not img:
        converted.info.pop("icc_profile", None)
    return converted
