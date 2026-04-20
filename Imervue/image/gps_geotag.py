"""GPS geotag writer — sets EXIF GPS coordinates on image files.

Uses ``piexif`` when available. Coordinates are stored as rationals in
deg/min/sec form with N/S and E/W refs. Reading back is handled by
:mod:`Imervue.image.gps` (already present in the codebase).
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("Imervue.gps_geotag")

_DEG_TO_SEC = 3600.0


def _to_rational(value: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """Convert a signed decimal-degree value to (deg, min, sec) rationals."""
    abs_val = abs(value)
    deg = int(abs_val)
    minutes_full = (abs_val - deg) * 60.0
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60.0
    # Use 10000 as denominator on seconds for 4-decimal precision.
    return (deg, 1), (minutes, 1), (int(round(seconds * 10000)), 10000)


def write_gps(path: str | Path, latitude: float, longitude: float) -> bool:
    """Write *latitude* / *longitude* (decimal degrees) into EXIF GPS tags.

    Returns True on success. Returns False if ``piexif`` is unavailable or
    the file format does not support EXIF writes (PNG, TIFF via piexif).
    """
    try:
        import piexif
    except ImportError:
        logger.info("piexif not installed — skipping GPS write for %s", path)
        return False
    p = Path(path)
    if not p.is_file():
        return False
    try:
        exif_dict = piexif.load(str(p))
    except (ValueError, OSError, piexif.InvalidImageDataError):
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    lat_ref = b"N" if latitude >= 0 else b"S"
    lon_ref = b"E" if longitude >= 0 else b"W"
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: _to_rational(latitude),
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: _to_rational(longitude),
    }
    exif_dict["GPS"] = gps_ifd
    try:
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(p))
    except (ValueError, OSError) as err:
        logger.warning("Failed to write GPS for %s: %s", p, err)
        return False
    return True
