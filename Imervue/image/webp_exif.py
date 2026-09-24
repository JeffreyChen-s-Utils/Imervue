"""Rewrite a WebP's EXIF chunk without re-encoding it — Pillow only, no piexif.

A WebP is a RIFF container of chunks; its EXIF lives in its own ``EXIF``
chunk, which only the extended layout (a leading ``VP8X`` chunk with the
EXIF flag set) may carry. An edit swaps that one chunk, promoting a simple
``VP8 `` / ``VP8L`` file to the extended layout when it has none, so the
image data stays byte for byte. The chunk holds the TIFF block without the
``Exif\\0\\0`` header, per the WebP container spec (and as Pillow writes it).
"""
from __future__ import annotations

import struct
from collections.abc import Callable

from PIL import Image

from Imervue.image.jpeg_exif import EXIF_HEADER, load_exif, serialize_exif

_RIFF, _WEBP = b"RIFF", b"WEBP"
_VP8X, _VP8, _VP8L = b"VP8X", b"VP8 ", b"VP8L"
_EXIF, _XMP = b"EXIF", b"XMP "
_FLAG_EXIF, _FLAG_ALPHA = 0x08, 0x10
_VP8L_SIGNATURE = 0x2F
_VP8_START_CODE = b"\x9d\x01\x2a"
_MAX_DIMENSION = 1 << 24


def _chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """``(fourcc, payload)`` for each chunk of a WebP; ValueError for anything else."""
    if len(data) < 12 or data[:4] != _RIFF or data[8:12] != _WEBP:
        raise ValueError("not a WebP")
    chunks = []
    pos = 12
    while pos + 8 <= len(data):
        fourcc = data[pos:pos + 4]
        (size,) = struct.unpack("<I", data[pos + 4:pos + 8])
        end = pos + 8 + size
        if end > len(data):
            raise ValueError(f"truncated WebP chunk {fourcc!r}")
        chunks.append((fourcc, data[pos + 8:end]))
        pos = end + (size & 1)
    if not chunks:
        raise ValueError("WebP without chunks")
    return chunks


def _riff(chunks: list[tuple[bytes, bytes]]) -> bytes:
    body = b"".join(fourcc + struct.pack("<I", len(payload)) + payload + b"\0" * (len(payload) & 1)
                    for fourcc, payload in chunks)
    return _RIFF + struct.pack("<I", 4 + len(body)) + _WEBP + body


def _canvas(fourcc: bytes, payload: bytes) -> tuple[int, int, bool]:
    """``(width, height, has_alpha)`` read from a simple file's bitstream header."""
    if fourcc == _VP8L and len(payload) >= 5 and payload[0] == _VP8L_SIGNATURE:
        (bits,) = struct.unpack("<I", payload[1:5])
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, bool((bits >> 28) & 1)
    if fourcc == _VP8 and len(payload) >= 10 and payload[3:6] == _VP8_START_CODE:
        width, height = struct.unpack("<HH", payload[6:10])
        return width & 0x3FFF, height & 0x3FFF, False
    raise ValueError(f"unrecognised WebP bitstream {fourcc!r}")


def _vp8x(width: int, height: int, flags: int) -> tuple[bytes, bytes]:
    if not (0 < width <= _MAX_DIMENSION and 0 < height <= _MAX_DIMENSION):
        raise ValueError(f"WebP canvas {width}x{height} out of range")
    size = struct.pack("<I", width - 1)[:3] + struct.pack("<I", height - 1)[:3]
    return _VP8X, bytes([flags, 0, 0, 0]) + size


def _extended(chunks: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """*chunks* in the extended layout: a simple file gains a leading ``VP8X``."""
    first, payload = chunks[0]
    if first == _VP8X:
        return list(chunks)
    width, height, alpha = _canvas(first, payload)
    return [_vp8x(width, height, _FLAG_ALPHA if alpha else 0), *chunks]


def update_webp_exif(data: bytes, update: Callable[[Image.Exif], None]) -> bytes:
    """Return WebP *data* with *update* applied to its EXIF; the image data stays byte-exact.

    *update* mutates the parsed EXIF in place (an empty one when the file has
    none). The new chunk replaces the old one, or goes after the image data
    and before any XMP chunk, as the container spec orders them. Raises
    ``ValueError`` for data that isn't a WebP, a truncated chunk table, an
    unrecognised bitstream or an unreadable EXIF block.
    """
    chunks = _extended(_chunks(data))
    found = next((i for i, (fourcc, _p) in enumerate(chunks) if fourcc == _EXIF), None)
    original = None
    if found is not None:
        stored = chunks[found][1]
        original = stored if stored.startswith(EXIF_HEADER) else EXIF_HEADER + stored
    exif = load_exif(original)
    update(exif)
    chunk = (_EXIF, serialize_exif(exif, original)[len(EXIF_HEADER):])
    if found is not None:
        chunks[found] = chunk
    else:
        at = next((i for i, (fourcc, _p) in enumerate(chunks) if fourcc == _XMP), len(chunks))
        chunks.insert(at, chunk)
    flags = chunks[0][1][0] | _FLAG_EXIF
    chunks[0] = (_VP8X, bytes([flags]) + chunks[0][1][1:])
    return _riff(chunks)
