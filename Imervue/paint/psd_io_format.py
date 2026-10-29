"""PSD format primitives shared by the reader and the writer.

Header / channel / blend-mode / layer-flag / compression / section-divider
constants, the bounds-checked byte :class:`_Cursor` the reader walks, the
PackBits RLE row decoder, Pascal-string pack / read helpers and the
channel-id to RGBA-plane mapping. :mod:`Imervue.paint.psd_io` re-exports
every name here.
"""
from __future__ import annotations

import struct

import numpy as np

PSD_SIGNATURE = b"8BPS"
PSD_VERSION = 1
PSD_DEPTH_8BIT = 8
PSD_COLOR_MODE_RGB = 3
PSD_CHANNELS_RGBA = 4

# Channel ids per Photoshop spec: 0..2 = R/G/B, -1 = transparency mask.
CHANNEL_ORDER = (0, 1, 2, -1)
CHANNEL_NAMES = {0: "R", 1: "G", 2: "B", -1: "A"}

# Blend-mode keys per Photoshop spec (4 ASCII bytes).
_BLEND_MODE_TO_PSD = {
    "normal": b"norm",
    "multiply": b"mul ",
    "screen": b"scrn",
    "overlay": b"over",
    "darken": b"dark",
    "lighten": b"lite",
    "color_dodge": b"div ",
    "color_burn": b"idiv",
    "soft_light": b"sLit",
    "hard_light": b"hLit",
    "linear_burn": b"lbrn",
    "linear_dodge": b"lddg",
}
_PSD_TO_BLEND_MODE = {v: k for k, v in _BLEND_MODE_TO_PSD.items()}

# Layer-record flags (bit values, big-endian byte).
_LAYER_FLAG_TRANSPARENCY_PROTECTED = 0x01
_LAYER_FLAG_HIDDEN = 0x02
# Bit 3 must be 1 to indicate Photoshop 5.0+ flag layout (otherwise bit
# 4 is reserved). We always set it on write.
_LAYER_FLAG_PHOTOSHOP_5_PLUS = 0x08

# Compression types in channel / image data sections.
_COMPRESSION_RAW = 0
_COMPRESSION_RLE = 1

# Section-divider types — used by ``lsct`` to mark layer groups.
_SECTION_OTHER = 0
_SECTION_OPEN_GROUP = 1
_SECTION_CLOSED_GROUP = 2
_SECTION_END = 3
_SECTION_END_NAME = "</Layer group>"


def _channel_plane(image: np.ndarray, channel_id: int) -> np.ndarray:
    """Map PSD channel ID → numpy slice on an HxWx4 RGBA array."""
    if channel_id == -1:
        return np.ascontiguousarray(image[..., 3])
    return np.ascontiguousarray(image[..., channel_id])


def _pack_pascal_padded(name: str, *, pad_to: int) -> bytes:
    """Pascal string (1-byte length + bytes) padded so total is a
    multiple of ``pad_to``."""
    encoded = name.encode("latin-1", errors="replace")
    if len(encoded) > 255:
        encoded = encoded[:255]
    payload = bytes([len(encoded)]) + encoded
    pad_len = (-len(payload)) % pad_to
    return payload + b"\x00" * pad_len


# ---------------------------------------------------------------------------
# PackBits RLE decode
# ---------------------------------------------------------------------------


def _packbits_decode(raw: bytes, expected_length: int) -> np.ndarray:
    """Decode one PackBits RLE row into a uint8 ndarray.

    PackBits convention (Apple / TIFF / PSD):

    * n in [0, 127]   — copy next ``n + 1`` bytes literally
    * n in [-127, -1] — repeat next byte ``-n + 1`` times
    * n == -128       — no-op (skipped)
    """
    out = bytearray()
    i = 0
    raw_len = len(raw)
    while i < raw_len:
        header = raw[i]
        i += 1
        if header < 128:
            run_len = header + 1
            out.extend(raw[i:i + run_len])
            i += run_len
        elif header == 128:
            continue
        else:
            run_len = 257 - header
            if i >= raw_len:
                break
            out.extend(bytes([raw[i]]) * run_len)
            i += 1
    if len(out) != expected_length:
        # Tolerate a slightly-short row by zero-padding rather than
        # raising — some encoders pad differently.
        if len(out) < expected_length:
            out.extend(b"\x00" * (expected_length - len(out)))
        else:
            del out[expected_length:]
    return np.frombuffer(bytes(out), dtype=np.uint8)


def _read_pascal_padded(cursor, *, pad_to: int) -> str:
    length = cursor.read_u8()
    name_bytes = cursor.read(length)
    total = 1 + length
    pad = (-total) % pad_to
    cursor.skip(pad)
    return name_bytes.decode("latin-1", errors="replace")


# ---------------------------------------------------------------------------
# Cursor helper
# ---------------------------------------------------------------------------


class _Cursor:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0

    def read(self, n: int) -> bytes:
        if self.pos + n > len(self.buf):
            raise ValueError(
                f"PSD truncated: tried to read {n} bytes at offset {self.pos} "
                f"of {len(self.buf)}",
            )
        out = self.buf[self.pos:self.pos + n]
        self.pos += n
        return out

    def skip(self, n: int) -> None:
        self.pos = min(self.pos + max(0, int(n)), len(self.buf))

    def seek(self, pos: int) -> None:
        self.pos = max(0, min(int(pos), len(self.buf)))

    def read_u8(self) -> int:
        return self.read(1)[0]

    def read_u16(self) -> int:
        return struct.unpack(">H", self.read(2))[0]

    def read_i16(self) -> int:
        return struct.unpack(">h", self.read(2))[0]

    def read_u32(self) -> int:
        return struct.unpack(">I", self.read(4))[0]

    def read_i32(self) -> int:
        return struct.unpack(">i", self.read(4))[0]
