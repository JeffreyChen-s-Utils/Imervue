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
from pathlib import Path

from PIL import Image

from Imervue.image.in_place_save import (
    can_rewrite_in_place, carried_save_kwargs, in_place_format,
)
from Imervue.system.atomic_write import replace_atomically
from Imervue.image.jpeg_orientation import set_jpeg_orientation
from Imervue.image.orientation import (
    exif_orientation, read_orientation, transpose_for,
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
            save_kwargs = carried_save_kwargs(img, fmt, file_path)
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
