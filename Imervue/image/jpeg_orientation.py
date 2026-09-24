"""Change a JPEG's EXIF orientation without re-encoding it — a truly lossless turn.

A quarter turn of a JPEG only needs a new EXIF orientation value; re-encoding
the pixels loses quality and, through Pillow, every metadata tag it isn't
handed back. This rewrites just the orientation, byte-exact everywhere else
when the tag already exists, and needs nothing beyond Pillow (``piexif`` is
not a dependency).

Pure bytes-in / bytes-out; the caller writes the result.
"""
from __future__ import annotations

import struct

from PIL import Image

_SOI = b"\xff\xd8"
_APP0 = 0xE0
_APP1 = 0xE1
_SOS = 0xDA
_EOI = 0xD9
_STANDALONE_MARKERS = frozenset({0x01, *range(0xD0, 0xD8)})   # TEM, RST0-7: no length field
_EXIF_HEADER = b"Exif\x00\x00"
_ORIENTATION_TAG = 0x0112
_SHORT = 3
_MAX_SEGMENT_PAYLOAD = 0xFFFF - 2


def set_jpeg_orientation(data: bytes, code: int) -> bytes:
    """Return JPEG *data* with its EXIF orientation set to *code* (1–8).

    An existing orientation entry is patched in place, so every other byte —
    maker notes, thumbnail, pixels — stays as it was. A JPEG whose EXIF lacks
    the tag gets its EXIF re-serialised with the tag added (the IFD1 thumbnail
    is dropped); one without EXIF gets a new EXIF segment. Raises
    ``ValueError`` for data that isn't a JPEG, a malformed segment table, an
    EXIF block Pillow can't parse, or a *code* outside 1–8.
    """
    if not 1 <= code <= 8:
        raise ValueError(f"EXIF orientation must be 1-8, got {code}")
    if not data.startswith(_SOI):
        raise ValueError("not a JPEG")
    segments = _header_segments(data)
    exif = next(((start, end) for marker, start, end in segments
                 if marker == _APP1 and data[start + 4:start + 10] == _EXIF_HEADER), None)
    if exif is None:
        at = next((end for marker, _start, end in segments[:1] if marker == _APP0), len(_SOI))
        return data[:at] + _app1(_exif_payload(Image.Exif(), code)) + data[at:]
    start, end = exif
    payload = data[start + 4:end]
    patched = _patch_orientation(payload, code)
    if patched is None:
        rebuilt = Image.Exif()
        try:
            rebuilt.load(payload)
        except SyntaxError as err:   # Pillow's error for an EXIF block without a TIFF header
            raise ValueError("unreadable EXIF block") from err
        patched = _exif_payload(rebuilt, code)
    return data[:start] + _app1(patched) + data[end:]


def _header_segments(data: bytes) -> list[tuple[int, int, int]]:
    """Return ``(marker, start, end)`` for each length-carrying segment before the scan."""
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


def _patch_orientation(payload: bytes, code: int) -> bytes | None:
    """Return EXIF *payload* with its IFD0 orientation set; None if it has none to patch."""
    tiff = payload[len(_EXIF_HEADER):]
    order = {b"II": "<", b"MM": ">"}.get(tiff[:2])
    if order is None or len(tiff) < 8:
        return None
    (ifd0,) = struct.unpack(order + "I", tiff[4:8])
    if ifd0 + 2 > len(tiff):
        return None
    (count,) = struct.unpack(order + "H", tiff[ifd0:ifd0 + 2])
    for index in range(count):
        entry = ifd0 + 2 + 12 * index
        if entry + 12 > len(tiff):
            return None
        tag, kind, values = struct.unpack(order + "HHI", tiff[entry:entry + 8])
        if tag == _ORIENTATION_TAG:
            if kind != _SHORT or values != 1:
                return None
            at = len(_EXIF_HEADER) + entry + 8
            return payload[:at] + struct.pack(order + "H", code) + payload[at + 2:]
    return None


def _exif_payload(exif: Image.Exif, code: int) -> bytes:
    exif[_ORIENTATION_TAG] = code
    return exif.tobytes()


def _app1(payload: bytes) -> bytes:
    if len(payload) > _MAX_SEGMENT_PAYLOAD:
        raise ValueError("EXIF block too large for one JPEG segment")
    return b"\xff" + bytes([_APP1]) + struct.pack(">H", len(payload) + 2) + payload
