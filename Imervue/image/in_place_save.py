"""Which files can be edited and written back over themselves, and in which format.

Pillow opens more than it can faithfully write back. It reads a camera RAW
(CR2 / NEF / DNG …) as its small embedded TIFF preview, and an animated GIF /
WebP / APNG or a multi-page TIFF as its first frame. Saving the edited pixels
back over such a file destroys it: a 9 MB CR2 became a 0.8 MB preview-sized
TIFF. Every in-place writer (rotate, Modify's apply-crop, the annotation
editor's Save) asks :func:`can_rewrite_in_place` first.
"""
from __future__ import annotations

import os
import struct
from collections.abc import Callable
from pathlib import Path

from PIL import Image, JpegImagePlugin, PngImagePlugin

from Imervue.image.orientation import strip_xmp_orientation
from Imervue.image.read_errors import IMAGE_READ_ERRORS

_IN_PLACE_FORMATS: dict[str, str] = {
    ".png": "PNG",
    ".jpg": "JPEG", ".jpeg": "JPEG", ".jpe": "JPEG", ".jfif": "JPEG",
    ".bmp": "BMP",
    ".tif": "TIFF", ".tiff": "TIFF",
    ".webp": "WEBP",
    ".gif": "GIF",
}

_XMP_TAG = 700
_INTEROP_POINTER = 0xA005
_SUB_IFDS = (0x8769, 0x8825)   # Exif, GPS
# IFD0 tags that describe the picture rather than lay out its pixels:
# DocumentName, ImageDescription, Make, Model, PageName, Software, DateTime,
# Artist, HostComputer, XMP, Rating, RatingPercent, Copyright, IPTC, XP*.
_DESCRIPTIVE_IFD0_TAGS = frozenset({
    269, 270, 271, 272, 285, 305, 306, 315, 316, _XMP_TAG, 18246, 18249,
    33432, 33723, 40091, 40092, 40093, 40094, 40095,
})


def in_place_format(path: str | Path) -> str | None:
    """Return the Pillow format to write *path* back in, or ``None`` if it can't be."""
    return _IN_PLACE_FORMATS.get(Path(path).suffix.lower())


def replace_atomically(path: str | Path, write: Callable[[Path], None]) -> None:
    """Replace *path* with what *write* puts in a ``.tmp`` sibling, in one step.

    A crash or an error mid-write leaves the original whole: the sibling is
    removed and the error propagates. *write* gets the sibling's path, whose
    extension is ``.tmp``, so a Pillow save must name its ``format=``.
    """
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    try:
        write(tmp)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def can_rewrite_in_place(path: str | Path) -> bool:
    """Whether decoding *path*, editing the pixels and saving it back keeps the file whole.

    False for formats Pillow cannot write back faithfully (camera RAW, HEIC,
    JPEG XL, SVG, video), for multi-frame files (animated GIF / WebP / APNG,
    multi-page TIFF, MPO), whose other frames a single-image save would drop,
    and for a file that can't be read at all.
    """
    if in_place_format(path) is None:
        return False
    try:
        with Image.open(path) as img:
            return getattr(img, "n_frames", 1) == 1
    except IMAGE_READ_ERRORS:
        return False


def webp_is_lossless(file_path: str) -> bool:
    """Whether the WebP at *file_path* holds a lossless (VP8L) bitstream."""
    with open(file_path, "rb") as handle:
        data = handle.read()
    pos = 12   # past "RIFF" <size> "WEBP"
    while pos + 8 <= len(data):
        fourcc = data[pos:pos + 4]
        if fourcc in (b"VP8L", b"VP8 "):
            return fourcc == b"VP8L"
        (size,) = struct.unpack("<I", data[pos + 4:pos + 8])
        pos += 8 + size + (size & 1)
    return False


def descriptive_exif(source: Image.Image) -> Image.Exif:
    """Copy *source*'s descriptive EXIF — IFD0 text tags plus the Exif and GPS IFDs.

    A TIFF's ``getexif()`` is its whole tag directory, width, strip offsets and
    all; handed back to the save, those tags overwrite the new layout (a turned
    40x20 TIFF came back 40x40). The orientation is left out: the turn is baked
    into the pixels.
    """
    exif = source.getexif()
    kept = Image.Exif()
    for tag in _DESCRIPTIVE_IFD0_TAGS & exif.keys():
        value = exif[tag]
        kept[tag] = strip_xmp_orientation(value) if tag == _XMP_TAG else value
    for pointer in _SUB_IFDS:
        entries = {k: v for k, v in exif.get_ifd(pointer).items() if k != _INTEROP_POINTER}
        if entries:
            kept.get_ifd(pointer).update(entries)
            kept[pointer] = 0   # the save writes the IFD and its real offset
    return kept


def carried_save_kwargs(source: Image.Image, fmt: str, file_path: str) -> dict:
    """Pillow save options that carry *source*'s metadata and compression into a rewrite.

    *source* is the open file at *file_path*, *fmt* the format it is written
    back in (see :func:`in_place_format`). Carries descriptive EXIF without the
    orientation, ICC profile, DPI, XMP and PNG text without their orientation,
    the JPEG quantisation tables and subsampling, WebP's lossless mode and
    TIFF compression.
    """
    kwargs: dict = {}
    exif = descriptive_exif(source)
    if len(exif):
        kwargs["exif"] = exif
    for key in ("icc_profile", "dpi"):
        if source.info.get(key):
            kwargs[key] = source.info[key]
    if source.info.get("xmp") and fmt in ("JPEG", "WEBP"):
        kwargs["xmp"] = strip_xmp_orientation(source.info["xmp"])
    if fmt == "JPEG":
        kwargs["qtables"] = source.quantization
        kwargs["subsampling"] = JpegImagePlugin.get_sampling(source)
    elif fmt == "PNG" and getattr(source, "text", None):
        text = PngImagePlugin.PngInfo()
        for key, value in source.text.items():
            text.add_itxt(key, strip_xmp_orientation(value))
        kwargs["pnginfo"] = text
    elif fmt == "WEBP":
        kwargs.update({"lossless": True} if webp_is_lossless(file_path) else {"quality": 90})
    elif fmt == "TIFF" and any(pointer in exif for pointer in _SUB_IFDS):
        # Pillow's compressing (libtiff) writer can't write the Exif / GPS IFDs;
        # a bigger file beats losing the capture date and location for good.
        kwargs["compression"] = "raw"
    return kwargs
