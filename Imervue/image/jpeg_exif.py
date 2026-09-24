"""Rewrite a JPEG's EXIF block without touching its pixels — Pillow only.

``piexif`` is not a dependency, and saving through Pillow re-encodes the
image. A JPEG's EXIF lives in one APP1 segment, so an edit only needs that
segment swapped: every other byte stays as it was.

Pillow can load and re-serialise an EXIF block (IFD0 with its Exif, GPS and
Interop IFDs, maker notes included), but ``Image.Exif.tobytes`` drops IFD1,
the embedded thumbnail other programs show before decoding the full image.
:func:`serialize_exif` re-attaches it. Pure bytes in, bytes out; the caller
writes the file.
"""
from __future__ import annotations

import struct
from collections.abc import Callable

from PIL import ExifTags, Image, TiffImagePlugin

_SOI = b"\xff\xd8"
_APP0 = 0xE0
_APP1 = 0xE1
_SOS = 0xDA
_EOI = 0xD9
_STANDALONE_MARKERS = frozenset({0x01, *range(0xD0, 0xD8)})   # TEM, RST0-7: no length field
EXIF_HEADER = b"Exif\x00\x00"
_MAX_SEGMENT_PAYLOAD = 0xFFFF - 2
_THUMB_OFFSET = 513   # JPEGInterchangeFormat
_THUMB_LENGTH = 514   # JPEGInterchangeFormatLength


def header_segments(data: bytes) -> list[tuple[int, int, int]]:
    """Return ``(marker, start, end)`` for each length-carrying segment before the scan.

    Raises ``ValueError`` for data that isn't a JPEG or whose segment table is
    malformed or truncated.
    """
    if not data.startswith(_SOI):
        raise ValueError("not a JPEG")
    segments = []
    pos = len(_SOI)
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            raise ValueError(f"no JPEG marker at byte {pos}")
        marker = data[pos + 1]
        if marker == 0xFF:            # fill byte before the marker
            pos += 1
            continue
        if marker in (_SOS, _EOI):
            return segments
        if marker in _STANDALONE_MARKERS:
            pos += 2
            continue
        (length,) = struct.unpack(">H", data[pos + 2:pos + 4])
        end = pos + 2 + length
        if length < 2 or end > len(data):
            raise ValueError(f"truncated JPEG segment at byte {pos}")
        segments.append((marker, pos, end))
        pos = end
    raise ValueError("JPEG ends before its image data")


def exif_segment(data: bytes) -> tuple[int, int] | None:
    """Return ``(start, end)`` of JPEG *data*'s EXIF APP1 segment, or None without one."""
    return next(((start, end) for marker, start, end in header_segments(data)
                 if marker == _APP1 and data[start + 4:start + 10] == EXIF_HEADER), None)


def replace_exif_segment(data: bytes, payload: bytes) -> bytes:
    """Return JPEG *data* with its EXIF segment holding *payload* (``Exif\\0\\0`` + TIFF).

    A JPEG without EXIF gets the segment after its JFIF header (which must
    stay first) or right after the start-of-image marker. Raises
    ``ValueError`` for a payload too large for one segment.
    """
    if len(payload) > _MAX_SEGMENT_PAYLOAD:
        raise ValueError("EXIF block too large for one JPEG segment")
    segment = b"\xff" + bytes([_APP1]) + struct.pack(">H", len(payload) + 2) + payload
    found = exif_segment(data)
    if found is not None:
        start, end = found
        return data[:start] + segment + data[end:]
    first = header_segments(data)[:1]
    at = first[0][2] if first and first[0][0] == _APP0 else len(_SOI)
    return data[:at] + segment + data[at:]


def load_exif(payload: bytes | None) -> Image.Exif:
    """Parse an EXIF *payload* into an ``Image.Exif``; empty for None.

    Raises ``ValueError`` for a block without a valid TIFF header.
    """
    exif = Image.Exif()
    if payload:
        try:
            exif.load(payload)
        except SyntaxError as err:   # Pillow's error for a block without a TIFF header
            raise ValueError("unreadable EXIF block") from err
    return exif


def serialize_exif(exif: Image.Exif, original: bytes | None = None) -> bytes:
    """Serialise *exif* to an EXIF payload, keeping *original*'s IFD1 thumbnail.

    ``Image.Exif.tobytes`` writes IFD0 and its sub-IFDs but not IFD1; the
    thumbnail directory and image are copied from *original* (a payload as
    stored in the file) and chained after IFD0.
    """
    payload = exif.tobytes()
    thumbnail = _thumbnail_of(original)
    if thumbnail is None:
        return payload
    ifd1, image = thumbnail
    tiff = bytearray(payload[len(EXIF_HEADER):])
    order = "<" if tiff[:2] == b"II" else ">"
    (ifd0,) = struct.unpack(order + "I", tiff[4:8])
    (count,) = struct.unpack(order + "H", tiff[ifd0:ifd0 + 2])
    next_pointer = ifd0 + 2 + 12 * count
    if len(tiff) % 2:
        tiff += b"\0"             # IFDs start on a word boundary
    at = len(tiff)
    block = _ifd_bytes(ifd1, bytes(tiff[:2]), at, thumb_at=0)
    block = _ifd_bytes(ifd1, bytes(tiff[:2]), at, thumb_at=at + len(block))
    struct.pack_into(order + "I", tiff, next_pointer, at)
    return EXIF_HEADER + bytes(tiff) + block + image


def _thumbnail_of(original: bytes | None) -> tuple[dict, bytes] | None:
    """IFD1's tags and its JPEG thumbnail from an EXIF payload; None without one."""
    if not original:
        return None
    try:
        source = load_exif(original)
        ifd1 = dict(source.get_ifd(ExifTags.IFD.IFD1))
    except (ValueError, OSError, struct.error, KeyError):   # a broken IFD1: no thumbnail to keep
        return None
    offset, length = ifd1.get(_THUMB_OFFSET), ifd1.get(_THUMB_LENGTH)
    if not offset or not length:
        return None
    tiff = original[len(EXIF_HEADER):]
    image = tiff[offset:offset + length]
    if len(image) != length or not image.startswith(_SOI):
        return None
    return ifd1, image


def _ifd_bytes(tags: dict, byte_order: bytes, at: int, *, thumb_at: int) -> bytes:
    ifd = TiffImagePlugin.ImageFileDirectory_v2(prefix=byte_order)
    for tag, value in tags.items():
        ifd[tag] = value
    ifd[_THUMB_OFFSET] = thumb_at
    return ifd.tobytes(at)


def update_jpeg_exif(data: bytes, update: Callable[[Image.Exif], None]) -> bytes:
    """Return JPEG *data* with *update* applied to its EXIF; the pixels stay byte-exact.

    *update* mutates the parsed EXIF in place (an empty one when the file has
    none). The thumbnail is kept. Raises ``ValueError`` for data that isn't a
    JPEG, an unreadable EXIF block, or a result too large for one segment.
    """
    found = exif_segment(data)
    original = data[found[0] + 4:found[1]] if found else None
    exif = load_exif(original)
    update(exif)
    return replace_exif_segment(data, serialize_exif(exif, original))
