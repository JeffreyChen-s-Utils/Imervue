"""Tests for GPS geotag writer."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("piexif")

from PIL import Image

from Imervue.image import gps_geotag


def _make_jpeg(tmp_path: Path) -> Path:
    p = tmp_path / "test.jpg"
    Image.new("RGB", (20, 20), color=(128, 128, 128)).save(p, "JPEG")
    return p


class TestWriteGps:
    def test_writes_the_required_gps_version(self, tmp_path):
        import piexif
        path = _make_jpeg(tmp_path)
        assert gps_geotag.write_gps(path, 1.0, 2.0) is True
        assert piexif.load(str(path))["GPS"][piexif.GPSIFD.GPSVersionID] == (2, 3, 0, 0)

    @pytest.mark.parametrize(("lat", "lon"), [
        (90.0001, 0.0), (-90.0001, 0.0), (0.0, 180.0001), (0.0, -180.0001), (float("nan"), 0.0),
    ])
    def test_out_of_range_coordinates_are_rejected(self, tmp_path, lat, lon):
        path = _make_jpeg(tmp_path)
        with pytest.raises(ValueError, match="out of range"):
            gps_geotag.write_gps(path, lat, lon)

    @pytest.mark.parametrize(("lat", "lon"), [(90.0, 180.0), (-90.0, -180.0)])
    def test_the_range_limits_themselves_are_written(self, tmp_path, lat, lon):
        from Imervue.image.gps import extract_gps
        path = _make_jpeg(tmp_path)
        assert gps_geotag.write_gps(path, lat, lon) is True
        assert extract_gps(path) == pytest.approx((lat, lon))

    def test_returns_false_for_missing_file(self, tmp_path):
        assert gps_geotag.write_gps(tmp_path / "missing.jpg", 10.0, 20.0) is False

    def test_round_trip_through_reader(self, tmp_path):
        path = _make_jpeg(tmp_path)
        ok = gps_geotag.write_gps(path, 25.033, 121.565)   # Taipei
        assert ok is True

        import piexif
        exif = piexif.load(str(path))
        gps_ifd = exif.get("GPS", {})
        assert gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef) == b"N"
        assert gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef) == b"E"

    def test_negative_coords_use_s_and_w_refs(self, tmp_path):
        path = _make_jpeg(tmp_path)
        gps_geotag.write_gps(path, -33.8688, -70.6693)   # Santiago (lon negative)

        import piexif
        exif = piexif.load(str(path))
        gps_ifd = exif.get("GPS", {})
        assert gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef) == b"S"
        assert gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef) == b"W"


class TestToRational:
    def test_deg_min_sec_structure(self):
        deg, minutes, seconds = gps_geotag._to_rational(1.5)
        assert deg == (1, 1)
        assert minutes == (30, 1)
        assert seconds[0] >= 0
