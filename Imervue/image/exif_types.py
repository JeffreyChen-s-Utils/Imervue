"""Put back the TIFF types Pillow's EXIF writer gets wrong.

``Image.Exif.tobytes`` infers each entry's type from the Python value where
its tag tables have no entry: UNDEFINED blocks (MakerNote, UserComment,
ComponentsConfiguration, FileSource, SceneType, PrintIM) come out as BYTE,
and non-negative SRATIONALs (ShutterSpeedValue, ExposureBiasValue) as
RATIONAL. The bytes of each value are the same either way, so the fix is to
rewrite the type field of those entries: to the type the EXIF specification
gives the tag, else to the type the source file used. Only swaps
between types of the same element size are made, so no count or offset moves.
"""
from __future__ import annotations

import struct

EXIF_HEADER = b"Exif\x00\x00"

_BYTE, _ASCII, _SHORT, _LONG, _RATIONAL = 1, 2, 3, 4, 5
_SBYTE, _UNDEFINED, _SSHORT, _SLONG, _SRATIONAL = 6, 7, 8, 9, 10
_ELEMENT_SIZE = {
    _BYTE: 1, _ASCII: 1, _SHORT: 2, _LONG: 4, _RATIONAL: 8,
    _SBYTE: 1, _UNDEFINED: 1, _SSHORT: 2, _SLONG: 4, _SRATIONAL: 8,
    11: 4, 12: 8,   # FLOAT, DOUBLE
}

_EXIF_POINTER, _GPS_POINTER, _INTEROP_POINTER = 0x8769, 0x8825, 0xA005
# (pointer tag, IFD it sits in) → name of the IFD it points to
_CHILD_IFDS = {(_EXIF_POINTER, "0th"): "exif", (_GPS_POINTER, "0th"): "gps",
               (_INTEROP_POINTER, "exif"): "interop"}

# EXIF 2.32 types for the tags Pillow's tables leave to guesswork.
_SPEC_TYPES: dict[tuple[str, int], int] = {
    ("exif", 0x9000): _UNDEFINED,   # ExifVersion
    ("exif", 0x9101): _UNDEFINED,   # ComponentsConfiguration
    ("exif", 0x9201): _SRATIONAL,   # ShutterSpeedValue
    ("exif", 0x9203): _SRATIONAL,   # BrightnessValue
    ("exif", 0x9204): _SRATIONAL,   # ExposureBiasValue
    ("exif", 0x927C): _UNDEFINED,   # MakerNote
    ("exif", 0x9286): _UNDEFINED,   # UserComment
    ("exif", 0xA000): _UNDEFINED,   # FlashpixVersion
    ("exif", 0xA300): _UNDEFINED,   # FileSource
    ("exif", 0xA301): _UNDEFINED,   # SceneType
    ("exif", 0xA302): _UNDEFINED,   # CFAPattern
    ("exif", 0x8828): _UNDEFINED,   # OECF
    ("exif", 0xA20C): _UNDEFINED,   # SpatialFrequencyResponse
    ("exif", 0xA40B): _UNDEFINED,   # DeviceSettingDescription
    ("gps", 0x001B): _UNDEFINED,    # GPSProcessingMethod
    ("gps", 0x001C): _UNDEFINED,    # GPSAreaInformation
    ("interop", 0x0002): _UNDEFINED,   # InteroperabilityVersion
    ("0th", 0xC4A5): _UNDEFINED,    # PrintIM
}


def _entries(tiff: bytes, order: str):
    """Yield ``(ifd_name, tag, type, entry_offset)`` for IFD0, Exif, GPS and Interop."""
    (ifd0,) = struct.unpack(order + "I", tiff[4:8])
    pending = [("0th", ifd0)]
    seen = set()
    while pending:
        name, at = pending.pop()
        if at in seen or at + 2 > len(tiff):
            continue
        seen.add(at)
        (count,) = struct.unpack(order + "H", tiff[at:at + 2])
        for index in range(count):
            entry = at + 2 + 12 * index
            if entry + 12 > len(tiff):
                break
            tag, kind, _count, value = struct.unpack(order + "HHII", tiff[entry:entry + 12])
            yield name, tag, kind, entry
            child = _CHILD_IFDS.get((tag, name))
            if child is not None:
                pending.append((child, value))


def _parse(payload: bytes | None):
    """``(tiff, byte order)`` of an EXIF payload; None when it isn't one."""
    if not payload or not payload.startswith(EXIF_HEADER):
        return None
    tiff = payload[len(EXIF_HEADER):]
    order = {b"II": "<", b"MM": ">"}.get(tiff[:2])
    if order is None or len(tiff) < 8:
        return None
    return tiff, order


def entry_types(payload: bytes | None) -> dict[tuple[str, int], int]:
    """``(ifd_name, tag) → TIFF type`` for every entry of an EXIF payload ({} if unreadable)."""
    parsed = _parse(payload)
    if parsed is None:
        return {}
    try:
        return {(name, tag): kind for name, tag, kind, _entry in _entries(*parsed)}
    except struct.error:
        return {}


def restore_types(payload: bytes, original: bytes | None = None) -> bytes:
    """Return *payload* with each entry's type set back to the spec's or *original*'s.

    A type is only changed to another of the same element size (UNDEFINED ↔
    BYTE, SRATIONAL ↔ RATIONAL, …), so every count and offset stays valid.
    *payload* is returned unchanged when it isn't a parseable EXIF block.
    """
    parsed = _parse(payload)
    if parsed is None:
        return payload
    tiff, order = parsed
    # The spec wins for the tags it names: a source already written by an
    # earlier Pillow save may carry the same wrong type.
    wanted = {**entry_types(original), **_SPEC_TYPES}
    patched = bytearray(tiff)
    try:
        for name, tag, kind, entry in _entries(tiff, order):
            target = wanted.get((name, tag))
            if (target is not None and target != kind
                    and _ELEMENT_SIZE.get(target) == _ELEMENT_SIZE.get(kind)):
                struct.pack_into(order + "H", patched, entry + 2, target)
    except struct.error:
        return payload
    return EXIF_HEADER + bytes(patched)
