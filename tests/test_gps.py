"""Tests for GPS EXIF extraction."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

# piexif is the easiest way to craft EXIF GPS payloads in tests; skip
# cleanly when it is not installed (the GPS reader itself only needs PIL).
piexif = pytest.importorskip("piexif")

from Imervue.image import gps


def _rat(value: float) -> tuple[int, int]:
    """Return an EXIF rational approximation of a positive float."""
    denom = 1_000_000
    return (int(round(value * denom)), denom)


def _dms_rationals(degrees: float):
    d = int(abs(degrees))
    m_full = (abs(degrees) - d) * 60
    m = int(m_full)
    s = (m_full - m) * 60
    return [_rat(d), _rat(m), _rat(s)]


def _write_with_gps(path, lat, lon, lat_ref=None, lon_ref=None):
    if lat_ref is None:
        lat_ref = "N" if lat >= 0 else "S"
    if lon_ref is None:
        lon_ref = "E" if lon >= 0 else "W"
    exif_dict = {
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode(),
            piexif.GPSIFD.GPSLatitude: _dms_rationals(lat),
            piexif.GPSIFD.GPSLongitudeRef: lon_ref.encode(),
            piexif.GPSIFD.GPSLongitude: _dms_rationals(lon),
        }
    }
    exif_bytes = piexif.dump(exif_dict)
    img = Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8))
    img.save(str(path), format="JPEG", exif=exif_bytes)


class TestExtractGps:
    def test_no_exif_returns_none(self, tmp_path):
        p = tmp_path / "plain.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(p)
        assert gps.extract_gps(str(p)) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert gps.extract_gps(str(tmp_path / "ghost.jpg")) is None

    def test_northern_hemisphere_positive_latitude(self, tmp_path):
        p = tmp_path / "paris.jpg"
        _write_with_gps(p, 48.8566, 2.3522)
        coords = gps.extract_gps(str(p))
        assert coords is not None
        lat, lon = coords
        assert abs(lat - 48.8566) < 0.001
        assert abs(lon - 2.3522) < 0.001

    def test_southern_hemisphere_negative_latitude(self, tmp_path):
        p = tmp_path / "sydney.jpg"
        _write_with_gps(p, -33.8688, 151.2093)
        coords = gps.extract_gps(str(p))
        assert coords is not None
        assert coords[0] < 0
        assert coords[1] > 0

    def test_west_longitude_is_negative(self, tmp_path):
        p = tmp_path / "nyc.jpg"
        _write_with_gps(p, 40.7128, 74.0060, lat_ref="N", lon_ref="W")
        coords = gps.extract_gps(str(p))
        assert coords is not None
        assert coords[1] < 0


class TestCollectGps:
    def test_skips_images_without_gps(self, tmp_path):
        p1 = tmp_path / "no.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(p1)
        p2 = tmp_path / "yes.jpg"
        _write_with_gps(p2, 10.0, 20.0)
        out = gps.collect_gps([str(p1), str(p2)])
        assert len(out) == 1
        assert out[0][0] == str(p2)
