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

:func:`raw_xmp` finds their XMP packet (where a camera keeps its in-camera
rating) the same way: CR3's XMP ``uuid`` box, IFD0's XMP tag, the JPEG's XMP
APP1 segment.

Only the metadata is read, by seeking to it: a folder of RAW files is not read
through. Qt-free, so the MCP server can use it.
"""
from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image

from Imervue.image.raw_exif_cr3 import _cr3_exif, top_level_box
from Imervue.image.raw_exif_raf import _raf_exif, jpeg_app1, raf_jpeg_header
from Imervue.image.raw_exif_tiff import _tiff_exif

RAW_EXIF_EXTENSIONS: frozenset[str] = frozenset({".cr3", ".rw2", ".rwl", ".orf", ".raf"})
"""The RAW formats whose EXIF :func:`raw_exif` reads."""

_XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")   # Adobe's, CR3 uses it
_JPEG_XMP_SIGNATURE = b"http://ns.adobe.com/xap/1.0/" + bytes(1)
_TIFF_XMP_TAG = 700
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


def raw_xmp(path: str | Path) -> bytes | None:
    """Return the XMP packet of the CR3 / RW2 / RWL / ORF / RAF at *path*.

    ``None`` for another format and for a file without one or with damaged
    metadata; ``OSError`` only when the file itself can't be read.
    """
    ext = Path(path).suffix.lower()
    if ext not in RAW_EXIF_EXTENSIONS:
        return None
    if ext not in (".cr3", ".raf"):
        exif = raw_exif(path)
        packet = None if exif is None else exif.get(_TIFF_XMP_TAG)
        if isinstance(packet, str):
            packet = packet.encode("utf-8")
        return packet if isinstance(packet, bytes) and packet else None
    with open(path, "rb") as handle:
        try:
            if ext == ".cr3":
                return top_level_box(handle, b"uuid", _XMP_UUID) or None
            jpeg = raf_jpeg_header(handle)
            app1 = None if jpeg is None else jpeg_app1(jpeg, _JPEG_XMP_SIGNATURE)
            return None if app1 is None else app1[len(_JPEG_XMP_SIGNATURE):] or None
        except _BAD_METADATA:
            return None
