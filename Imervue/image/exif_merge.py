"""One ``{tag: value}`` view of a Pillow image's EXIF, whatever the format.

``Image.getexif()`` returns IFD0 only. Most camera fields (DateTimeOriginal,
ExposureTime, FNumber, ISO, FocalLength, LensModel) live in the Exif sub-IFD,
and coordinates in the GPS sub-IFD. JPEG / PNG / WebP images also have a
private ``_getexif()`` that merges them; HEIC and JPEG XL images do not.

:func:`read_exif` reads a file's EXIF whatever the format, camera RAW
containers Pillow can't open included; :func:`get_exif_data` gives it by tag
name. Both are Qt-free, so the MCP server and the library use them as well as
the viewer's panels.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image
from PIL.ExifTags import TAGS

from Imervue.image.formats import ensure_pillow_opener
from Imervue.image.raw_exif import RAW_EXIF_EXTENSIONS, raw_exif
from Imervue.image.read_errors import IMAGE_READ_ERRORS

logger = logging.getLogger("Imervue.image.exif_merge")


_SUB_IFDS = (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo)


def read_exif(path: str | Path) -> Image.Exif:
    """Return the EXIF of the file at *path*, its Exif and GPS IFDs already read.

    An empty :class:`~PIL.Image.Exif` when it has none or can't be read. The
    camera RAW containers Pillow can't open (CR3, RW2, ORF, RAF) go through
    :func:`~Imervue.image.raw_exif.raw_exif`, the rest through Pillow with the
    HEIC / JPEG XL codec registered. The sub-IFDs are read while the file is
    open: a TIFF-based file (NEF, CR2, DNG) reads them from the file on
    demand, which failed with "seek of closed file" once it was closed.
    """
    ext = Path(path).suffix.lower()
    try:
        if ext in RAW_EXIF_EXTENSIONS:
            return raw_exif(path) or Image.Exif()
        ensure_pillow_opener(ext)
        with Image.open(path) as img:
            exif = img.getexif()
            for pointer in _SUB_IFDS:
                if pointer in exif:
                    exif.get_ifd(pointer)
            return exif
    except IMAGE_READ_ERRORS:
        logger.debug("EXIF read failed for %s", path, exc_info=True)
        return Image.Exif()


def merged_exif(source: Image.Image | Image.Exif) -> dict[int, Any]:
    """Return IFD0 plus the Exif sub-IFD, with the GPS sub-IFD nested under ``GPSInfo``.

    The same shape Pillow's own ``_getexif()`` builds, so JPEG results match it.
    *source* is an open image or an EXIF read with :func:`read_exif`.
    """
    exif = source if isinstance(source, Image.Exif) else source.getexif()
    merged: dict[int, Any] = dict(exif)
    merged.update(exif.get_ifd(ExifTags.IFD.Exif))
    if ExifTags.IFD.GPSInfo in exif:
        merged[ExifTags.IFD.GPSInfo] = dict(exif.get_ifd(ExifTags.IFD.GPSInfo))
    return merged


def get_exif_data(path: Path):
    """Return ``{tag name: value}`` for *path*, or ``{}`` when it has no EXIF or cannot be read."""
    try:
        exif_raw = merged_exif(read_exif(path))
        if not exif_raw:
            return {}

        return {
            TAGS.get(tag, tag): value
            for tag, value in exif_raw.items()
        }

    except Exception:  # noqa: BLE001 - PIL's EXIF parser fails in open-ended ways; logged below
        logger.debug("EXIF read failed for %s", path, exc_info=True)
        return {}
