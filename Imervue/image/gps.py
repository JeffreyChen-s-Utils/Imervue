"""
GPS extraction from EXIF.

Reads the standard GPS IFD (``GPSInfo`` tag 0x8825) from JPEG / TIFF /
HEIC / CR2 / NEF EXIF, converts the degrees-minutes-seconds rationals
into signed decimal (positive = N/E, negative = S/W), and returns a
``(latitude, longitude)`` tuple — or ``None`` when any required field
is missing.

The parser is defensive: any malformed or missing GPS sub-tag drops the
whole record rather than returning partial data, since half a coordinate
is worse than no coordinate for clustering on a map.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import ExifTags, Image

logger = logging.getLogger("Imervue.gps")


# Cache the ExifTags reverse lookup so we can decode GPSInfo sub-keys.
_GPSTAGS = {v: k for k, v in ExifTags.GPSTAGS.items()} if hasattr(
    ExifTags, "GPSTAGS",
) else {}
_GPS_IFD_TAG = 0x8825


def _rationals_to_degrees(parts) -> float | None:
    """Convert EXIF (d, m, s) rational triple to decimal degrees."""
    try:
        d, m, s = parts
        return float(d) + float(m) / 60.0 + float(s) / 3600.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def extract_gps(path: str | Path) -> tuple[float, float] | None:
    """Return (lat, lon) in signed decimal degrees, or ``None`` if absent."""
    try:
        with Image.open(path) as im:
            exif = im.getexif()
    except (OSError, ValueError):
        return None
    if not exif:
        return None

    gps = None
    try:
        gps = exif.get_ifd(_GPS_IFD_TAG)
    except (AttributeError, KeyError, ValueError, OSError):
        gps = None
    if not gps:
        # Some HEIC / older images expose GPSInfo via _getexif() directly.
        raw = exif.get(_GPS_IFD_TAG)
        if isinstance(raw, dict):
            gps = raw
    if not gps:
        return None

    lat = _rationals_to_degrees(gps.get(2))
    lon = _rationals_to_degrees(gps.get(4))
    if lat is None or lon is None:
        return None
    lat_ref = str(gps.get(1, "N")).strip().upper()
    lon_ref = str(gps.get(3, "E")).strip().upper()
    if lat_ref == "S":
        lat = -lat
    if lon_ref == "W":
        lon = -lon
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        return None
    return (lat, lon)


def collect_gps(paths: list[str | Path]) -> list[tuple[str, float, float]]:
    """Return a list of (path, lat, lon) tuples, skipping items without GPS."""
    out: list[tuple[str, float, float]] = []
    for p in paths:
        coords = extract_gps(p)
        if coords is not None:
            lat, lon = coords
            out.append((str(p), lat, lon))
    return out
