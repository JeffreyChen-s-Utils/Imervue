"""One ``{tag: value}`` view of a Pillow image's EXIF, whatever the format.

``Image.getexif()`` returns IFD0 only. Most camera fields (DateTimeOriginal,
ExposureTime, FNumber, ISO, FocalLength, LensModel) live in the Exif sub-IFD,
and coordinates in the GPS sub-IFD. JPEG / PNG / WebP images also have a
private ``_getexif()`` that merges them; HEIC and JPEG XL images do not.

:func:`get_exif_data` reads it by tag name from a file; it is Qt-free, so the
MCP server and the library use it as well as the viewer's panels.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image
from PIL.ExifTags import TAGS

from Imervue.image.formats import ensure_pillow_opener

logger = logging.getLogger("Imervue.image.exif_merge")


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


def get_exif_data(path: Path):
    """Return ``{tag name: value}`` for *path*, or ``{}`` when it has no EXIF or cannot be read."""
    ensure_pillow_opener(Path(path).suffix)
    try:
        with Image.open(path) as img:
            exif_raw = merged_exif(img)

        if not exif_raw:
            return {}

        return {
            TAGS.get(tag, tag): value
            for tag, value in exif_raw.items()
        }

    except Exception:  # noqa: BLE001 - PIL's EXIF parser fails in open-ended ways; logged below
        logger.debug("EXIF read failed for %s", path, exc_info=True)
        return {}
