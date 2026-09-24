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


def exif_block(order: str, exif_entries: list[tuple[int, int, bytes]],
           ifd0_entries: list[tuple[int, int, bytes]] = ()) -> bytes:
    """A hand-built EXIF payload: IFD0 (+ entries) pointing at an Exif IFD."""
    head = (b"II" if order == "<" else b"MM") + struct.pack(order + "HI", 42, 8)
    ifd0_count = len(ifd0_entries) + 1
    exif_at = 8 + 2 + 12 * ifd0_count + 4
    exif_size = 2 + 12 * len(exif_entries) + 4
    data_at = exif_at + exif_size
    data = b""

    def entry(tag, kind, value):
        nonlocal data
        size = {1: 1, 2: 1, 5: 8, 7: 1, 10: 8}[kind]
        count = len(value) // size
        if len(value) <= 4:
            return struct.pack(order + "HHI", tag, kind, count) + value.ljust(4, b"\0")
        offset = data_at + len(data)
        data += value
        return struct.pack(order + "HHII", tag, kind, count, offset)

    ifd0 = struct.pack(order + "H", ifd0_count)
    for tag, kind, value in ifd0_entries:
        ifd0 += entry(tag, kind, value)
    ifd0 += struct.pack(order + "HHII", 0x8769, 4, 1, exif_at) + struct.pack(order + "I", 0)
    exif = struct.pack(order + "H", len(exif_entries))
    for tag, kind, value in exif_entries:
        exif += entry(tag, kind, value)
    exif += struct.pack(order + "I", 0)
    return b"Exif\x00\x00" + head + ifd0 + exif + data


def rational_bytes(order: str, num: int, den: int) -> bytes:
    """A (S)RATIONAL value's 8 bytes."""
    return struct.pack(order + "ii" if num < 0 else order + "II", num, den)
