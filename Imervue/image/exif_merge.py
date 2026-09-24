"""One ``{tag: value}`` view of a Pillow image's EXIF, whatever the format.

``Image.getexif()`` returns IFD0 only. Most camera fields (DateTimeOriginal,
ExposureTime, FNumber, ISO, FocalLength, LensModel) live in the Exif sub-IFD,
and coordinates in the GPS sub-IFD. JPEG / PNG / WebP images also have a
private ``_getexif()`` that merges them; HEIC and JPEG XL images do not.
"""
from __future__ import annotations

from typing import Any

from PIL import ExifTags, Image


def merged_exif(img: Image.Image) -> dict[int, Any]:
    """Return IFD0 plus the Exif sub-IFD, with the GPS sub-IFD nested under ``GPSInfo``.

    The same shape Pillow's own ``_getexif()`` builds, so JPEG results match it.
    """
    exif = img.getexif()
    merged: dict[int, Any] = dict(exif)
    merged.update(exif.get_ifd(ExifTags.IFD.Exif))
    if ExifTags.IFD.GPSInfo in exif:
        merged[ExifTags.IFD.GPSInfo] = dict(exif.get_ifd(ExifTags.IFD.GPSInfo))
    return merged
