"""Which files can be edited and written back over themselves, and in which format.

Pillow opens more than it can faithfully write back. It reads a camera RAW
(CR2 / NEF / DNG …) as its small embedded TIFF preview, and an animated GIF /
WebP / APNG or a multi-page TIFF as its first frame. Saving the edited pixels
back over such a file destroys it: a 9 MB CR2 became a 0.8 MB preview-sized
TIFF. Every in-place writer (rotate, Modify's apply-crop and annotation save,
the annotation editor's Save) asks :func:`can_rewrite_in_place` first, and
writes through :func:`save_over_source` or :func:`carried_save_kwargs` so the
file keeps its metadata.
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

_JPEG_COLOUR_TABLES = 2   # luma + chroma quantisation tables
_XMP_TAG = 700
_INTEROP_POINTER = 0xA005
# Exif IFD tags a rewrite makes wrong: the Interop pointer's offset, PixelX/YDimension.
_STALE_SUB_IFD_TAGS = frozenset({_INTEROP_POINTER, 0xA002, 0xA003})
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


def descriptive_exif(source: Image.Image, *, keep_location: bool = True) -> Image.Exif:
    """Copy *source*'s descriptive EXIF — IFD0 text tags plus the Exif and GPS IFDs.

    A TIFF's ``getexif()`` is its whole tag directory, width, strip offsets and
    all; handed back to the save, those tags overwrite the new layout (a turned
    40x20 TIFF came back 40x40). Also left out: the orientation (the turn is
    baked into the pixels) and the Exif IFD's pixel dimensions, which an edit
    changes. Without *keep_location* the GPS IFD and the XMP packet (which can
    repeat the position) are dropped too.
    """
    exif = source.getexif()
    kept = Image.Exif()
    for tag in _DESCRIPTIVE_IFD0_TAGS & exif.keys():
        if tag == _XMP_TAG and not keep_location:
            continue
        value = exif[tag]
        kept[tag] = strip_xmp_orientation(value) if tag == _XMP_TAG else value
    for pointer in _SUB_IFDS if keep_location else _SUB_IFDS[:1]:
        entries = {k: v for k, v in exif.get_ifd(pointer).items()
                   if k not in _STALE_SUB_IFD_TAGS}
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


def save_over_source(path: str | Path, edited: Image.Image) -> None:
    """Write *edited* over the file at *path*, keeping the file's descriptive metadata.

    *edited* holds pixels as the viewer decodes them — upright and in sRGB —
    so the source's orientation and ICC profile are not carried; its EXIF
    (camera, capture date, GPS), DPI, XMP, PNG text and compression are. The
    file is replaced in one step, so a failed save leaves it whole. Raises
    ``ValueError`` for a file :func:`can_rewrite_in_place` refuses, and what
    Pillow raises (``IMAGE_READ_ERRORS``) when the save fails.
    """
    if not can_rewrite_in_place(path):
        raise ValueError(f"{path} can't be saved back whole")
    save_edited_copy(path, edited, path)


def save_edited_copy(source_path: str | Path, edited: Image.Image, target: str | Path) -> None:
    """Write *edited*, made from *source_path*, to *target* with the source's metadata.

    The format follows *target*'s extension. A target in the source's own
    format gets everything :func:`save_over_source` keeps; another format
    gets the descriptive EXIF and DPI, which every writable format can hold.
    An unreadable source just contributes nothing. Written in one step.
    Raises ``ValueError`` for a *target* extension Imervue can't write, and
    what Pillow raises when the save fails.
    """
    fmt = in_place_format(target)
    if fmt is None:
        raise ValueError(f"can't write {target}: unsupported extension")
    kwargs = _edited_save_kwargs(source_path, fmt)
    out = edited
    if fmt == "JPEG":
        if out.mode not in ("RGB", "L", "CMYK"):
            out = out.convert("RGB")
        if len(kwargs.get("qtables", ())) < _JPEG_COLOUR_TABLES and out.mode != "L":
            # No source tables, or a greyscale source's lone luma table.
            kwargs.pop("qtables", None)
            kwargs.pop("subsampling", None)
            kwargs["quality"] = 95
    replace_atomically(target, lambda tmp: out.save(tmp, format=fmt, **kwargs))


def _edited_save_kwargs(source_path: str | Path, fmt: str) -> dict:
    """Save options carrying *source_path*'s metadata into edited pixels written as *fmt*."""
    try:
        with Image.open(source_path) as source:
            if in_place_format(source_path) == fmt:
                kwargs = carried_save_kwargs(source, fmt, str(source_path))
            else:
                exif = descriptive_exif(source)
                kwargs = {"exif": exif} if len(exif) else {}
                if source.info.get("dpi"):
                    kwargs["dpi"] = source.info["dpi"]
    except IMAGE_READ_ERRORS:
        return {"quality": 90} if fmt == "WEBP" else {}
    kwargs.pop("icc_profile", None)   # the edited pixels are sRGB
    if fmt == "WEBP" and "lossless" not in kwargs:
        kwargs.setdefault("quality", 90)
    return kwargs
