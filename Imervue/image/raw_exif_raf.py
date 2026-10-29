"""The RAF side of :mod:`Imervue.image.raw_exif`: the camera JPEG a Fujifilm RAW embeds.

Its APP1 segments carry the EXIF and the XMP packet; only the JPEG's markers
before the image data are read.
"""
from __future__ import annotations

import struct
from typing import BinaryIO

from PIL import Image

from Imervue.image.raw_exif_tiff import _ifd0

# The JPEG markers before the image data: APP segments are 64 KB at most.
_JPEG_HEADER_BYTES = 512 * 1024
_RAF_MAGIC = b"FUJIFILMCCD-RAW "
_RAF_JPEG_POINTER = 84


def raf_jpeg_header(handle: BinaryIO) -> bytes | None:
    """The start of the camera JPEG a RAF embeds (its markers before the image data), or None."""
    header = handle.read(_RAF_JPEG_POINTER + 8)
    if not header.startswith(_RAF_MAGIC):
        return None
    offset, length = struct.unpack_from(">II", header, _RAF_JPEG_POINTER)
    handle.seek(offset)
    return handle.read(min(length, _JPEG_HEADER_BYTES))


def _raf_exif(handle: BinaryIO) -> Image.Exif | None:
    jpeg = raf_jpeg_header(handle)
    app1 = None if jpeg is None else jpeg_app1(jpeg, b"Exif\x00\x00")
    return None if app1 is None else _ifd0(app1)


def jpeg_app1(jpeg: bytes, signature: bytes) -> bytes | None:
    """The first APP1 payload of *jpeg* that starts with *signature*.

    Only the markers before the image data are searched.
    """
    if not jpeg.startswith(b"\xff\xd8"):
        return None
    pos = 2
    while pos + 4 <= len(jpeg) and jpeg[pos] == 0xFF:
        marker = jpeg[pos + 1]
        (size,) = struct.unpack_from(">H", jpeg, pos + 2)
        payload = jpeg[pos + 4:pos + 2 + size]
        if marker == 0xE1 and payload.startswith(signature):
            return payload
        if marker == 0xDA:   # start of scan: no metadata past it
            return None
        pos += 2 + size
    return None
