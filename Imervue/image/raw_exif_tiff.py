"""The TIFF side of :mod:`Imervue.image.raw_exif`: RW2 / RWL / ORF and Pillow's EXIF loads.

RW2 / RWL (Panasonic, Leica) and ORF (Olympus) are TIFF files whose header
carries the maker's own magic number instead of 42; :func:`_tiff_exif` reads
them through Pillow by seeking. The small Pillow helpers here also load the
bare TIFF blobs that CR3 boxes and a RAF's JPEG carry.
"""
from __future__ import annotations

import io
import warnings
from typing import BinaryIO

from PIL import ExifTags, Image

# Panasonic keeps its RAW parameters (sensor size, the embedded JPEG itself)
# in IFD0 under private tags below the TIFF baseline ones; one is the ISO.
_FIRST_BASELINE_TAG = 0x00FE
_PANASONIC_ISO = 0x0017


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
