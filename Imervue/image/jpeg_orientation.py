"""Change a JPEG's EXIF orientation without re-encoding it — a truly lossless turn.

A quarter turn of a JPEG only needs a new EXIF orientation value; re-encoding
the pixels loses quality and, through Pillow, every metadata tag it isn't
handed back. This rewrites just the orientation, byte-exact everywhere else
when the tag already exists, and needs nothing beyond Pillow (``piexif`` is
not a dependency). Segment handling lives in :mod:`jpeg_exif`.

Pure bytes-in / bytes-out; the caller writes the result.
"""
from __future__ import annotations

import struct

from Imervue.image.jpeg_exif import (
    EXIF_HEADER, exif_segment, load_exif, replace_exif_segment, serialize_exif,
)

_ORIENTATION_TAG = 0x0112
_SHORT = 3


def set_jpeg_orientation(data: bytes, code: int) -> bytes:
    """Return JPEG *data* with its EXIF orientation set to *code* (1–8).

    An existing orientation entry is patched in place, so every other byte —
    maker notes, thumbnail, pixels — stays as it was. A JPEG whose EXIF lacks
    the tag gets its EXIF re-serialised with the tag added (thumbnail kept);
    one without EXIF gets a new EXIF segment. Raises ``ValueError`` for data
    that isn't a JPEG, a malformed segment table, an EXIF block Pillow can't
    parse, or a *code* outside 1–8.
    """
    if not 1 <= code <= 8:
        raise ValueError(f"EXIF orientation must be 1-8, got {code}")
    found = exif_segment(data)
    original = data[found[0] + 4:found[1]] if found else None
    patched = _patch_orientation(original, code) if original else None
    if patched is None:
        exif = load_exif(original)
        exif[_ORIENTATION_TAG] = code
        patched = serialize_exif(exif, original)
    return replace_exif_segment(data, patched)


def _patch_orientation(payload: bytes, code: int) -> bytes | None:
    """Return EXIF *payload* with its IFD0 orientation set; None if it has none to patch."""
    tiff = payload[len(EXIF_HEADER):]
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
            at = len(EXIF_HEADER) + entry + 8
            return payload[:at] + struct.pack(order + "H", code) + payload[at + 2:]
    return None
