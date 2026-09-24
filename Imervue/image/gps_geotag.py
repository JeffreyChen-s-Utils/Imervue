"""GPS geotag writer — sets EXIF GPS coordinates on image files.

A JPEG gets its EXIF segment rewritten through Pillow (``jpeg_exif``), so
the pixels, the other tags and the thumbnail stay as they were and no extra
package is needed. Other formats fall back to ``piexif`` when it is
installed (it can also write WebP). Coordinates are stored as rationals in
deg/min/sec form with N/S and E/W refs. Reading back is handled by
:mod:`Imervue.image.gps` (already present in the codebase).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL.TiffImagePlugin import IFDRational

from Imervue.image.in_place_save import in_place_format, replace_atomically
from Imervue.image.jpeg_exif import update_jpeg_exif

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

    Returns True on success; False for a missing file, a write that failed,
    or a non-JPEG file when ``piexif`` is not installed (or can't write that
    format either). Any GPS tags already there are replaced. Raises
    ``ValueError`` for a latitude outside [-90, 90] or a longitude outside
    [-180, 180]: written as-is they are unreadable, so every GPS reader would
    drop them.
    """
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        raise ValueError(f"coordinates out of range: {latitude}, {longitude}")
    p = Path(path)
    if not p.is_file():
        return False
    if in_place_format(p) == "JPEG":
        return _write_jpeg_gps(p, latitude, longitude)
    return _write_with_piexif(p, latitude, longitude)


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


def _write_jpeg_gps(p: Path, latitude: float, longitude: float) -> bool:
    def set_gps(exif) -> None:
        gps = exif.get_ifd(_GPS_IFD)
        gps.clear()
        gps.update(_gps_entries(latitude, longitude))
        exif[_GPS_IFD] = 0   # the save writes the IFD and its real offset

    try:
        rewritten = update_jpeg_exif(p.read_bytes(), set_gps)
        replace_atomically(p, lambda tmp: tmp.write_bytes(rewritten))
    except (ValueError, OSError) as err:
        logger.warning("Failed to write GPS for %s: %s", p, err)
        return False
    return True


def _write_with_piexif(p: Path, latitude: float, longitude: float) -> bool:
    try:
        import piexif
    except ImportError:
        logger.info("piexif not installed — can't write GPS into %s", p)
        return False
    try:
        exif_dict = piexif.load(str(p))
    except (ValueError, OSError, piexif.InvalidImageDataError):
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    lat_ref, lon_ref = _refs(latitude, longitude)
    exif_dict["GPS"] = {
        _GPS_VERSION_ID: _GPS_VERSION,
        _GPS_LATITUDE_REF: lat_ref.encode(),
        _GPS_LATITUDE: _to_rational(latitude),
        _GPS_LONGITUDE_REF: lon_ref.encode(),
        _GPS_LONGITUDE: _to_rational(longitude),
    }
    try:
        piexif.insert(piexif.dump(exif_dict), str(p))
    except (ValueError, OSError) as err:
        logger.warning("Failed to write GPS for %s: %s", p, err)
        return False
    return True
