"""Hand-built EXIF blocks for the JPEG EXIF tests (no piexif, no code under test)."""
from __future__ import annotations

import io
import struct

from PIL import ExifTags, Image

from Imervue.image.jpeg_exif import exif_segment, load_exif

_MAKE = 0x010F


def thumbnail_jpeg() -> bytes:
    """A tiny JPEG to stand in for a camera thumbnail."""
    buf = io.BytesIO()
    Image.new("RGB", (8, 6), (10, 200, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def payload_with_thumbnail(order: str = "<") -> bytes:
    """A hand-built EXIF block: IFD0 (Make) chained to IFD1 (thumbnail offset / length)."""
    make = b"Canon\x00"
    thumb = thumbnail_jpeg()
    ifd0_at, make_at = 8, 8 + 2 + 12 + 4
    ifd1_at = make_at + len(make)
    thumb_at = ifd1_at + 2 + 2 * 12 + 4
    head = (b"II" if order == "<" else b"MM") + struct.pack(order + "HI", 42, ifd0_at)
    ifd0 = struct.pack(order + "H", 1) + struct.pack(order + "HHII", _MAKE, 2, len(make), make_at)
    ifd0 += struct.pack(order + "I", ifd1_at)
    ifd1 = struct.pack(order + "H", 2)
    ifd1 += struct.pack(order + "HHII", 513, 4, 1, thumb_at)
    ifd1 += struct.pack(order + "HHII", 514, 4, 1, len(thumb))
    ifd1 += struct.pack(order + "I", 0)
    return b"Exif\x00\x00" + head + ifd0 + make + ifd1 + thumb


def thumbnail_of(data: bytes) -> bytes | None:
    """The IFD1 thumbnail stored in JPEG *data*'s EXIF; None without one."""
    start, end = exif_segment(data)
    payload = data[start + 4:end]
    ifd1 = load_exif(payload).get_ifd(ExifTags.IFD.IFD1)
    if 513 not in ifd1:
        return None
    tiff = payload[6:]
    return tiff[ifd1[513]:ifd1[513] + ifd1[514]]
