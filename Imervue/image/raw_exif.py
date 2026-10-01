"""EXIF of the camera RAW containers Pillow can't open: CR3, RW2 / RWL, ORF and RAF.

Pillow opens the TIFF-based RAWs (CR2, NEF, ARW, DNG, PEF, ...) as TIFF and
reads their EXIF with them. The others keep the same TIFF structures where
Pillow doesn't look:

* CR3 (ISO base media): Canon's metadata ``uuid`` box in ``moov`` holds
  ``CMT1`` (IFD0), ``CMT2`` (the Exif IFD) and ``CMT4`` (the GPS IFD), each a
  whole little-endian or big-endian TIFF.
* RW2 / RWL (Panasonic, Leica) and ORF (Olympus) are TIFF files whose header
  carries the maker's own magic number instead of 42.
* RAF (Fujifilm) embeds the camera's JPEG, whose APP1 segment is the EXIF.

Only the metadata is read, by seeking to it: a folder of RAW files is not read
through. Qt-free, so the MCP server can use it.
"""
from __future__ import annotations

import io
import struct
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from PIL import ExifTags, Image

RAW_EXIF_EXTENSIONS: frozenset[str] = frozenset({".cr3", ".rw2", ".rwl", ".orf", ".raf"})
"""The RAW formats whose EXIF :func:`raw_exif` reads."""

_CANON_METADATA_UUID = bytes.fromhex("85c0b687820f11e08111f4ce462b6a48")
# A metadata box or JPEG header larger than this is not metadata.
_MAX_METADATA_BYTES = 4 * 1024 * 1024
# The JPEG markers before the image data: APP segments are 64 KB at most.
_JPEG_HEADER_BYTES = 512 * 1024
_RAF_MAGIC = b"FUJIFILMCCD-RAW "
_RAF_JPEG_POINTER = 84
# Panasonic keeps its RAW parameters (sensor size, the embedded JPEG itself)
# in IFD0 under private tags below the TIFF baseline ones; one is the ISO.
_FIRST_BASELINE_TAG = 0x00FE
_PANASONIC_ISO = 0x0017
# Errors Pillow's EXIF parser and the box walk raise on damaged metadata.
_BAD_METADATA = (struct.error, SyntaxError, ValueError, KeyError, IndexError, TypeError)


def raw_exif(path: str | Path) -> Image.Exif | None:
    """Return the EXIF of the CR3 / RW2 / RWL / ORF / RAF at *path*.

    The Exif and GPS IFDs are filled in and reachable through ``get_ifd``.
    ``None`` for any other format and for a file whose metadata is missing or
    damaged; ``OSError`` only when the file itself can't be read.
    """
    ext = Path(path).suffix.lower()
    if ext not in RAW_EXIF_EXTENSIONS:
        return None
    with open(path, "rb") as handle:
        try:
            if ext == ".cr3":
                return _cr3_exif(handle)
            if ext == ".raf":
                return _raf_exif(handle)
            return _tiff_exif(handle, drop_private=ext in {".rw2", ".rwl"})
        except _BAD_METADATA:
            return None


def _quietly(load, *args) -> None:
    """Run a Pillow EXIF load; damage leaves tags out, and Pillow only warns about it."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)   # "Corrupt EXIF data"
        load(*args)


def _load(tiff: bytes) -> Image.Exif:
    exif = Image.Exif()
    _quietly(exif.load, tiff)
    return exif


def _ifd0(tiff: bytes) -> Image.Exif | None:
    """IFD0 of *tiff*, or ``None`` when not one tag of it could be read."""
    exif = _load(tiff)
    return exif if len(exif) else None


def _attach(exif: Image.Exif, pointer: int, entries: dict) -> None:
    """Make *entries* the sub-IFD *pointer* of *exif*, as a Pillow save expects it."""
    if not entries:
        return
    exif.get_ifd(pointer).update(entries)
    exif[pointer] = 0   # a save writes the IFD and its real offset


# ---------------------------------------------------------------------------
# CR3
# ---------------------------------------------------------------------------


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
        header = handle.read(24)
        size, found = struct.unpack_from(">I4s", header)
        skip = 8
        if size == 1:
            (size,) = struct.unpack_from(">Q", header, 8)
            skip = 16
        elif size == 0:
            size = end - pos
        if size < skip:
            return None
        if found == kind and (uuid is None or header[skip:skip + 16] == uuid):
            skip += 0 if uuid is None else 16
            if size - skip > _MAX_METADATA_BYTES:
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


# ---------------------------------------------------------------------------
# RW2 / RWL / ORF
# ---------------------------------------------------------------------------


class _TiffMagic(io.RawIOBase):
    """*handle* read as a TIFF: the maker's magic number in bytes 2-3 reads as 42.

    Pillow then reads each tag where it lies, by seeking, instead of needing
    the file's head in memory: one value cut short there (a Panasonic's
    embedded JPEG runs past the first megabyte) cost it the whole IFD.
    """

    def __init__(self, handle: BinaryIO, magic: bytes) -> None:
        super().__init__()
        self._handle = handle
        self._magic = magic

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        return self._handle.seek(offset, whence)

    def tell(self) -> int:
        return self._handle.tell()

    def readinto(self, buffer) -> int:
        start = self._handle.tell()
        data = self._handle.read(len(buffer))
        if start < 4:
            patched = bytearray(data)
            for pos in range(max(start, 2), min(start + len(data), 4)):
                patched[pos - start] = self._magic[pos - 2]
            data = bytes(patched)
        buffer[:len(data)] = data
        return len(data)


def _tiff_exif(handle: BinaryIO, *, drop_private: bool) -> Image.Exif | None:
    order = handle.read(2)
    if order not in (b"II", b"MM"):
        return None
    handle.seek(0)
    tiff = _TiffMagic(handle, b"*\x00" if order == b"II" else b"\x00*")
    exif = Image.Exif()
    _quietly(exif.load_from_fp, tiff)
    if not len(exif):
        return None
    for pointer in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo):
        if pointer in exif:
            _quietly(exif.get_ifd, pointer)   # read while the file is open
    if drop_private:
        _drop_panasonic_private(exif)
    return exif


def _drop_panasonic_private(exif: Image.Exif) -> None:
    """Drop Panasonic's IFD0 RAW tags, keeping the ISO the Exif IFD lacks."""
    iso = exif.get(_PANASONIC_ISO)
    for tag in [t for t in exif if t < _FIRST_BASELINE_TAG]:
        del exif[tag]
    if isinstance(iso, int) and ExifTags.IFD.Exif in exif:
        exif.get_ifd(ExifTags.IFD.Exif).setdefault(ExifTags.Base.ISOSpeedRatings, iso)


# ---------------------------------------------------------------------------
# RAF
# ---------------------------------------------------------------------------


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
