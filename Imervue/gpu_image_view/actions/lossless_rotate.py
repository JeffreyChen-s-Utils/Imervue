from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

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

# JPEG file signatures (SOI marker)
_JPEG_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".jpe", ".jfif"}


def _is_jpeg(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in _JPEG_EXTENSIONS


def _rotate_via_exif(file_path: str, clockwise: bool) -> bool:
    """Rotate a JPEG by modifying its EXIF Orientation tag (truly lossless).

    Returns True on success, False if piexif is unavailable or an error occurs.
    """
    try:
        import piexif
    except ImportError:
        logger.debug("piexif not available; falling back to PIL rotation")
        return False

    try:
        exif_dict = piexif.load(file_path)

        # Read current orientation (default to 1 = normal if absent)
        current_orientation = exif_dict.get("0th", {}).get(
            piexif.ImageIFD.Orientation, 1
        )

        rotation_map = CW_ORIENTATION_MAP if clockwise else CCW_ORIENTATION_MAP
        new_orientation = rotation_map.get(current_orientation, 6 if clockwise else 8)

        exif_dict.setdefault("0th", {})[piexif.ImageIFD.Orientation] = new_orientation

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, file_path)

        direction = "CW" if clockwise else "CCW"
        logger.info(
            f"Lossless EXIF rotate {direction}: orientation {current_orientation} -> "
            f"{new_orientation} for {file_path}"
        )
        return True
    except Exception as exc:
        logger.error(f"EXIF rotation failed for {file_path}: {exc}")
        return False


def _rotate_via_pil(file_path: str, clockwise: bool) -> bool:
    """Rotate an image using PIL transpose and re-save (lossy for compressed formats)."""
    try:
        img = Image.open(file_path)

        if clockwise:
            rotated = img.transpose(Image.Transpose.ROTATE_270)
        else:
            rotated = img.transpose(Image.Transpose.ROTATE_90)

        # Preserve original format
        fmt = img.format or Path(file_path).suffix.lstrip(".").upper()
        if fmt == "JPG":
            fmt = "JPEG"

        save_kwargs: dict = {}
        if fmt == "PNG":
            save_kwargs["compress_level"] = 6
        elif fmt == "JPEG":
            save_kwargs["quality"] = 95
            # Ensure RGB mode for JPEG
            if rotated.mode in ("RGBA", "P"):
                rotated = rotated.convert("RGB")
        elif fmt == "WEBP":
            save_kwargs["quality"] = 90

        rotated.save(file_path, format=fmt, **save_kwargs)

        direction = "CW" if clockwise else "CCW"
        logger.info(f"PIL rotate {direction}: {file_path}")
        return True
    except Exception as exc:
        logger.error(f"PIL rotation failed for {file_path}: {exc}")
        return False


def lossless_rotate(file_path: str, clockwise: bool = True) -> bool:
    """Rotate an image file by 90 degrees.

    For JPEG files, attempts a truly lossless rotation by modifying the EXIF
    Orientation tag via *piexif*.  Falls back to PIL transpose + re-save when
    piexif is not installed or for non-JPEG formats.

    Args:
        file_path: Absolute path to the image file.
        clockwise: If True rotate 90 degrees clockwise; otherwise counter-clockwise.

    Returns:
        True if the rotation was applied successfully, False otherwise.
    """
    if not Path(file_path).is_file():
        logger.error(f"File not found: {file_path}")
        return False

    # Attempt lossless EXIF rotation for JPEG files
    if _is_jpeg(file_path):
        if _rotate_via_exif(file_path, clockwise):
            return True
        # piexif unavailable or failed; fall through to PIL

    return _rotate_via_pil(file_path, clockwise)
