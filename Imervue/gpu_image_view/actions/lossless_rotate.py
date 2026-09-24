"""Quarter-turn an image file on disk, losing as little as the format allows.

A JPEG only has its EXIF orientation changed (``jpeg_orientation``), so its
pixels and every metadata tag stay byte-exact. Other formats are decoded,
turned and saved back over themselves with their metadata — EXIF (minus the
orientation, which the turn bakes in), ICC profile, DPI, PNG text — and their
compression settings carried over. Files a re-save can't keep whole (camera
RAW, HEIC, multi-frame) are refused. Every write replaces the file in one step.
"""
from __future__ import annotations

import logging
import struct
from pathlib import Path

from PIL import Image, JpegImagePlugin, PngImagePlugin

from Imervue.image.in_place_save import can_rewrite_in_place, in_place_format, replace_atomically
from Imervue.image.jpeg_orientation import set_jpeg_orientation
from Imervue.image.orientation import (
    exif_orientation, read_orientation, strip_xmp_orientation, transpose_for,
)
from Imervue.image.read_errors import IMAGE_READ_ERRORS

logger = logging.getLogger("Imervue.lossless_rotate")

# EXIF Orientation tag value after a 90-degree clockwise rotation.
# Maps current_orientation -> new_orientation.
CW_ORIENTATION_MAP: dict[int, int] = {
    1: 6,
    6: 3,
    3: 8,
    8: 1,
    2: 7,
    7: 4,
    4: 5,
    5: 2,
}

# Counter-clockwise is the inverse of clockwise.
CCW_ORIENTATION_MAP: dict[int, int] = {v: k for k, v in CW_ORIENTATION_MAP.items()}

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


def _rotate_jpeg_tag(file_path: str, clockwise: bool) -> bool:
    """Turn a JPEG by rewriting only its EXIF orientation; False if the file won't take it."""
    rotation_map = CW_ORIENTATION_MAP if clockwise else CCW_ORIENTATION_MAP
    current = read_orientation(file_path)
    new_orientation = rotation_map.get(current, 6 if clockwise else 8)
    try:
        rotated = set_jpeg_orientation(Path(file_path).read_bytes(), new_orientation)
        replace_atomically(file_path, lambda tmp: tmp.write_bytes(rotated))
    except (ValueError, OSError):
        logger.warning("EXIF rotation failed for %s", file_path, exc_info=True)
        return False
    logger.info("Lossless EXIF rotate %s: orientation %s -> %s for %s",
                "CW" if clockwise else "CCW", current, new_orientation, file_path)
    return True


def _webp_is_lossless(file_path: str) -> bool:
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


def _descriptive_exif(source: Image.Image) -> Image.Exif:
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


def _metadata_kwargs(source: Image.Image, fmt: str, file_path: str) -> dict:
    """Save options that carry *source*'s metadata and compression into the rewrite."""
    kwargs: dict = {}
    exif = _descriptive_exif(source)
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
        kwargs.update({"lossless": True} if _webp_is_lossless(file_path) else {"quality": 90})
    elif fmt == "TIFF" and any(pointer in exif for pointer in _SUB_IFDS):
        # Pillow's compressing (libtiff) writer can't write the Exif / GPS IFDs;
        # a bigger file beats losing the capture date and location for good.
        kwargs["compression"] = "raw"
    return kwargs


def _rotate_via_pil(file_path: str, clockwise: bool) -> bool:
    """Decode, turn from what is shown, and save back with the source's metadata."""
    fmt = in_place_format(file_path)
    if fmt is None:
        return False
    try:
        with Image.open(file_path) as img:
            # Turn from what the viewer shows: the rewrite drops the orientation
            # tag, and rotating the stored pixels of a tagged image would cancel out.
            upright = transpose_for(img, exif_orientation(img))
            rotated = upright.transpose(
                Image.Transpose.ROTATE_270 if clockwise else Image.Transpose.ROTATE_90)
            save_kwargs = _metadata_kwargs(img, fmt, file_path)
        replace_atomically(file_path, lambda tmp: rotated.save(tmp, format=fmt, **save_kwargs))
    except IMAGE_READ_ERRORS:
        logger.warning("PIL rotation failed for %s", file_path, exc_info=True)
        return False
    logger.info("PIL rotate %s: %s", "CW" if clockwise else "CCW", file_path)
    return True


def lossless_rotate(file_path: str, clockwise: bool = True) -> bool:
    """Rotate an image file by 90 degrees; True when the file on disk was turned.

    A JPEG gets a new EXIF orientation and nothing else changes. Other
    formats (and a JPEG whose segments can't be parsed) are re-saved with
    their metadata; a file a re-save can't keep whole — camera RAW, HEIC /
    JXL / SVG, multi-frame (see ``in_place_save.can_rewrite_in_place``) — is
    refused and left untouched.
    """
    if not Path(file_path).is_file():
        logger.error("File not found: %s", file_path)
        return False
    if in_place_format(file_path) == "JPEG" and _rotate_jpeg_tag(file_path, clockwise):
        return True
    if not can_rewrite_in_place(file_path):
        logger.warning("Refusing to rewrite %s: its format or frames can't be saved back whole",
                       file_path)
        return False
    return _rotate_via_pil(file_path, clockwise)
