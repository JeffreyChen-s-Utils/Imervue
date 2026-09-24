"""GPS geotag writer — sets EXIF GPS coordinates on image files.

A JPEG or WebP gets only its EXIF block rewritten, through Pillow
(``in_place_save.rewrite_exif``), so the image data, the other tags and the
thumbnail stay as they were and no extra package is needed. Coordinates are stored as rationals in
deg/min/sec form with N/S and E/W refs. Reading back is handled by
:mod:`Imervue.image.gps` (already present in the codebase).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL.TiffImagePlugin import IFDRational

from Imervue.image.in_place_save import can_rewrite_exif, rewrite_exif

logger = logging.getLogger("Imervue.gps_geotag")

_DEG_TO_SEC = 3600.0
# EXIF requires GPSVersionID whenever a GPS IFD is present; 2.3.0.0 is the EXIF 2.3 value.
_GPS_VERSION = (2, 3, 0, 0)
_GPS_IFD = 0x8825
_GPS_VERSION_ID = 0
_GPS_LATITUDE_REF = 1
_GPS_LATITUDE = 2
_GPS_LONGITUDE_REF = 3
_GPS_LONGITUDE = 4


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

    Returns True on success; False for a missing file, a format whose EXIF
    can't be rewritten in place (anything but JPEG and WebP), or a write that
    failed. Any GPS tags already there are replaced. Raises ``ValueError`` for
    a latitude outside [-90, 90] or a longitude outside [-180, 180]: written
    as-is they are unreadable, so every GPS reader would drop them.
    """
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        raise ValueError(f"coordinates out of range: {latitude}, {longitude}")
    p = Path(path)
    if not p.is_file() or not can_rewrite_exif(p):
        return False

    def set_gps(exif) -> None:
        gps = exif.get_ifd(_GPS_IFD)
        gps.clear()
        gps.update(_gps_entries(latitude, longitude))
        exif[_GPS_IFD] = 0   # the save writes the IFD and its real offset

    try:
        rewrite_exif(p, set_gps)
    except (ValueError, OSError) as err:
        logger.warning("Failed to write GPS for %s: %s", p, err)
        return False
    return True


def _refs(latitude: float, longitude: float) -> tuple[str, str]:
    return ("N" if latitude >= 0 else "S"), ("E" if longitude >= 0 else "W")


def _gps_entries(latitude: float, longitude: float) -> dict[int, object]:
    """Pillow GPS IFD entries (tag → value) for the coordinates, refs included."""
    lat_ref, lon_ref = _refs(latitude, longitude)
    return {
        _GPS_VERSION_ID: bytes(_GPS_VERSION),
        _GPS_LATITUDE_REF: lat_ref,
        _GPS_LATITUDE: tuple(IFDRational(*part) for part in _to_rational(latitude)),
        _GPS_LONGITUDE_REF: lon_ref,
        _GPS_LONGITUDE: tuple(IFDRational(*part) for part in _to_rational(longitude)),
    }
