"""Tests for GPS geotag writer."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

from Imervue.image import gps_geotag
from Imervue.image.gps import extract_gps

_GPS = 0x8825


def _make_jpeg(tmp_path: Path, **save_kwargs) -> Path:
    p = tmp_path / "test.jpg"
    Image.new("RGB", (20, 20), color=(128, 128, 128)).save(p, "JPEG", **save_kwargs)
    return p


def _gps_ifd(path) -> dict:
    with Image.open(path) as img:
        return dict(img.getexif().get_ifd(_GPS))


@pytest.fixture
def no_piexif(monkeypatch):
    """piexif is not a dependency: the default install has none."""
    monkeypatch.setitem(sys.modules, "piexif", None)


class TestWriteGps:
    def test_writes_the_required_gps_version(self, tmp_path):
        path = _make_jpeg(tmp_path)
        assert gps_geotag.write_gps(path, 1.0, 2.0) is True
        assert _gps_ifd(path)[0] == b"\x02\x03\x00\x00"

    @pytest.mark.parametrize(("lat", "lon"), [
        (90.0001, 0.0), (-90.0001, 0.0), (0.0, 180.0001), (0.0, -180.0001), (float("nan"), 0.0),
    ])
    def test_out_of_range_coordinates_are_rejected(self, tmp_path, lat, lon):
        path = _make_jpeg(tmp_path)
        with pytest.raises(ValueError, match="out of range"):
            gps_geotag.write_gps(path, lat, lon)

    @pytest.mark.parametrize(("lat", "lon"), [(90.0, 180.0), (-90.0, -180.0)])
    def test_the_range_limits_themselves_are_written(self, tmp_path, lat, lon):
        path = _make_jpeg(tmp_path)
        assert gps_geotag.write_gps(path, lat, lon) is True
        assert extract_gps(path) == pytest.approx((lat, lon))

    def test_returns_false_for_missing_file(self, tmp_path):
        assert gps_geotag.write_gps(tmp_path / "missing.jpg", 10.0, 20.0) is False

    def test_round_trip_through_reader(self, tmp_path):
        path = _make_jpeg(tmp_path)
        assert gps_geotag.write_gps(path, 25.033, 121.565) is True   # Taipei
        gps = _gps_ifd(path)
        assert (gps[1], gps[3]) == ("N", "E")
        assert extract_gps(path) == pytest.approx((25.033, 121.565), abs=1e-6)

    def test_negative_coords_use_s_and_w_refs(self, tmp_path):
        path = _make_jpeg(tmp_path)
        gps_geotag.write_gps(path, -33.8688, -70.6693)   # Santiago (lon negative)
        gps = _gps_ifd(path)
        assert (gps[1], gps[3]) == ("S", "W")
        assert extract_gps(path) == pytest.approx((-33.8688, -70.6693), abs=1e-6)


class TestWithoutPiexif:
    """The default install: a JPEG is tagged through Pillow alone."""

    def test_jpeg_is_tagged(self, tmp_path, no_piexif):
        path = _make_jpeg(tmp_path)
        assert gps_geotag.write_gps(path, 48.8584, 2.2945) is True
        assert extract_gps(path) == pytest.approx((48.8584, 2.2945), abs=1e-6)

    def test_pixels_and_other_tags_are_untouched(self, tmp_path, no_piexif):
        exif = Image.Exif()
        exif[0x010F] = "Canon"
        exif.get_ifd(0x8769)[0x9003] = "2020:01:02 03:04:05"
        path = _make_jpeg(tmp_path, exif=exif)
        before = path.read_bytes()
        assert gps_geotag.write_gps(path, 1.0, 2.0) is True
        after = path.read_bytes()
        scan = b"\xff\xda"
        assert after[after.index(scan):] == before[before.index(scan):]
        with Image.open(path) as img:
            assert img.getexif()[0x010F] == "Canon"
            assert img.getexif().get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"

    def test_existing_position_is_replaced(self, tmp_path, no_piexif):
        path = _make_jpeg(tmp_path)
        gps_geotag.write_gps(path, 10.0, 20.0)
        gps_geotag.write_gps(path, -1.5, -2.5)
        assert extract_gps(path) == pytest.approx((-1.5, -2.5), abs=1e-6)

    def test_corrupt_jpeg_is_reported_and_left_alone(self, tmp_path, no_piexif):
        path = tmp_path / "broken.jpg"
        path.write_bytes(b"\xff\xd8\xff\xe1\x00")        # a segment cut short
        assert gps_geotag.write_gps(path, 1.0, 2.0) is False
        assert path.read_bytes() == b"\xff\xd8\xff\xe1\x00"
        assert [f.name for f in tmp_path.iterdir()] == ["broken.jpg"]

    def test_other_formats_need_piexif(self, tmp_path, no_piexif):
        path = tmp_path / "a.webp"
        Image.new("RGB", (8, 8)).save(path)
        before = path.read_bytes()
        assert gps_geotag.write_gps(path, 1.0, 2.0) is False
        assert path.read_bytes() == before


def test_webp_goes_through_piexif_when_installed(tmp_path):
    pytest.importorskip("piexif")
    path = tmp_path / "a.webp"
    Image.new("RGB", (8, 8)).save(path)
    assert gps_geotag.write_gps(path, 12.5, -45.25) is True
    assert extract_gps(path) == pytest.approx((12.5, -45.25), abs=1e-6)


class TestToRational:
    def test_deg_min_sec_structure(self):
        deg, minutes, seconds = gps_geotag._to_rational(1.5)
        assert deg == (1, 1)
        assert minutes == (30, 1)
        assert seconds[0] >= 0


def test_geotag_keeps_the_camera_tag_types(tmp_path, no_piexif):
    """Pillow's writer turned UNDEFINED UserComment / MakerNote into BYTE and SRATIONAL into RATIONAL."""
    from _exif_samples import exif_block, rational_bytes

    from Imervue.image.exif_types import entry_types
    from Imervue.image.jpeg_exif import exif_segment
    block = exif_block(">", [
        (0x9286, 7, b"ASCII\0\0\0hi"), (0x927C, 7, b"maker-note-bytes"),
        (0x9204, 10, rational_bytes(">", 0, 1)),
    ])
    path = _make_jpeg(tmp_path, exif=block)
    assert gps_geotag.write_gps(path, 1.0, 2.0) is True
    data = path.read_bytes()
    start, end = exif_segment(data)
    types = entry_types(data[start + 4:end])
    assert (types[("exif", 0x9286)], types[("exif", 0x927C)], types[("exif", 0x9204)]) == (7, 7, 10)
