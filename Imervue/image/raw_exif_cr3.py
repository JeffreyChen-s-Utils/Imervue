"""The CR3 side of :mod:`Imervue.image.raw_exif`: ISO base media boxes.

Canon's metadata ``uuid`` box in ``moov`` holds ``CMT1`` (IFD0), ``CMT2`` (the
Exif IFD) and ``CMT4`` (the GPS IFD), each a whole TIFF. Only box headers are
read on the way to it.
"""
from __future__ import annotations

import io
import struct
from collections.abc import Iterator
from typing import BinaryIO

from PIL import ExifTags, Image

from Imervue.image.raw_exif_tiff import _attach, _ifd0, _load

_CANON_METADATA_UUID = bytes.fromhex("85c0b687820f11e08111f4ce462b6a48")
# A metadata box or JPEG header larger than this is not metadata.
_MAX_METADATA_BYTES = 4 * 1024 * 1024


def _boxes(data: bytes, start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
    """Yield ``(type, payload start, payload end)`` of the ISO-BMFF boxes in ``data[start:end]``."""
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack_from(">I4s", data, pos)
        header = 8
        if size == 1:
            (size,) = struct.unpack_from(">Q", data, pos + 8)
            header = 16
        elif size == 0:
            size = end - pos
        if size < header:
            return
        yield kind, pos + header, min(pos + size, end)
        pos += size


def _box_span(header: bytes, remaining: int) -> tuple[int, int] | None:
    """``(size, header length)`` of the ISO-BMFF box starting with *header*.

    *remaining* is how many bytes are left from the box's start; ``None`` when
    the box claims fewer bytes than its own header or more than are left.
    """
    (size,) = struct.unpack_from(">I", header)
    skip = 8
    if size == 1:
        (size,) = struct.unpack_from(">Q", header, 8)
        skip = 16
    elif size == 0:
        size = remaining
    if size < skip or size > remaining:
        return None
    return size, skip


def top_level_box(handle: BinaryIO, kind: bytes, uuid: bytes | None = None) -> bytes | None:
    """The payload of the first top-level ISO-BMFF box of type *kind* in the file *handle*.

    For a ``uuid`` box *uuid* picks which one, and the 16 bytes that name it are
    left out. Only box headers are read on the way; ``None`` when there is no
    such box or it is too large to be metadata.
    """
    handle.seek(0, io.SEEK_END)
    end = handle.tell()
    pos = 0
    while pos + 8 <= end:
        handle.seek(pos)
        header = handle.read(32)   # extended size plus a UUID needs all 32 bytes
        span = _box_span(header, end - pos)
        if span is None:
            return None
        size, skip = span
        if header[4:8] == kind and (uuid is None or header[skip:skip + 16] == uuid):
            skip += 0 if uuid is None else 16
            if size < skip or size - skip > _MAX_METADATA_BYTES:
                return None
            handle.seek(pos + skip)
            return handle.read(size - skip)
        pos += size
    return None


def _cr3_exif(handle: BinaryIO) -> Image.Exif | None:
    moov = top_level_box(handle, b"moov")
    if moov is None:
        return None
    blobs: dict[bytes, bytes] = {}
    for kind, start, end in _boxes(moov, 0, len(moov)):
        if kind == b"uuid" and moov[start:start + 16] == _CANON_METADATA_UUID:
            blobs = {k: moov[s:e] for k, s, e in _boxes(moov, start + 16, end)
                     if k in (b"CMT1", b"CMT2", b"CMT4")}
            break
    exif = _ifd0(blobs[b"CMT1"]) if b"CMT1" in blobs else None
    if exif is None:
        return None
    if b"CMT2" in blobs:
        _attach(exif, ExifTags.IFD.Exif, dict(_load(blobs[b"CMT2"])))
    if b"CMT4" in blobs:
        gps = dict(_load(blobs[b"CMT4"]))
        # A camera without a position still writes the version tag alone.
        if set(gps) - {ExifTags.GPS.GPSVersionID}:
            _attach(exif, ExifTags.IFD.GPSInfo, gps)
    return exif
