"""Tests for the export metadata policy."""
from __future__ import annotations

import pytest
from PIL import Image

from Imervue.image.export_metadata import (
    DEFAULT_METADATA_POLICY, METADATA_ALL, METADATA_NO_LOCATION, METADATA_NONE,
    export_exif, export_save_options, policy_or_default,
)

_DATE = "2020:01:02 03:04:05"


def _photo(tmp_path, *, xmp: bool = False):
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif[0x0112] = 6
    if xmp:
        exif[700] = b'<x exif:GPSLatitude="25,2.0N"/>'
    exif.get_ifd(0x8769).update({0x9003: _DATE, 0xA002: 40, 0xA003: 20})
    exif[0x8769] = 0
    exif.get_ifd(0x8825)[1] = "N"
    exif[0x8825] = 0
    path = tmp_path / ("photo.tif" if xmp else "photo.jpg")
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    return path


def test_all_keeps_camera_date_and_location_but_not_the_orientation(tmp_path):
    exif = export_exif(_photo(tmp_path), METADATA_ALL)
    assert exif[0x010F] == "Canon"
    assert exif.get_ifd(0x8769)[0x9003] == _DATE
    assert exif.get_ifd(0x8825)[1] == "N"
    assert 0x0112 not in exif


def test_pixel_dimensions_an_edit_changes_are_not_carried(tmp_path):
    exif_ifd = export_exif(_photo(tmp_path), METADATA_ALL).get_ifd(0x8769)
    assert 0xA002 not in exif_ifd and 0xA003 not in exif_ifd


def test_no_location_drops_gps_and_the_xmp_that_can_repeat_it(tmp_path):
    exif = export_exif(_photo(tmp_path, xmp=True), METADATA_NO_LOCATION)
    assert exif[0x010F] == "Canon"
    assert exif.get_ifd(0x8769)[0x9003] == _DATE
    assert 0x8825 not in exif
    assert 700 not in exif
    reread = Image.Exif()
    reread.load(exif.tobytes())
    assert not reread.get_ifd(0x8825)            # nothing left behind in the bytes


def test_none_carries_nothing(tmp_path):
    assert export_exif(_photo(tmp_path), METADATA_NONE) is None
    assert export_save_options(_photo(tmp_path), METADATA_NONE) == {}


def test_source_without_exif_or_unreadable_carries_nothing(tmp_path):
    plain = tmp_path / "plain.png"
    Image.new("RGB", (4, 4)).save(plain)
    assert export_exif(plain, METADATA_ALL) is None
    assert export_exif(tmp_path / "gone.jpg", METADATA_ALL) is None


@pytest.mark.parametrize(("value", "expected"), [
    (METADATA_ALL, METADATA_ALL), (METADATA_NONE, METADATA_NONE),
    ("bogus", DEFAULT_METADATA_POLICY), (None, DEFAULT_METADATA_POLICY), (3, DEFAULT_METADATA_POLICY),
])
def test_policy_or_default(value, expected):
    assert policy_or_default(value) == expected


def test_unknown_policy_falls_back_to_dropping_the_location(tmp_path):
    """A corrupted setting must not start leaking GPS."""
    exif = export_exif(_photo(tmp_path), "bogus")
    assert exif[0x010F] == "Canon" and 0x8825 not in exif


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WebP", "TIFF", "BMP"])
def test_save_options_round_trip_through_every_writer(tmp_path, fmt):
    from Imervue.image.save_formats import save_image
    options = export_save_options(_photo(tmp_path), METADATA_ALL)
    assert isinstance(options["exif"], bytes)
    out = tmp_path / f"out.{fmt.lower()}"
    save_image(Image.new("RGB", (20, 40)), str(out), fmt, 90, options)
    with Image.open(out) as img:
        if fmt == "BMP":                          # the format has nowhere to put EXIF
            assert not len(img.getexif())
        else:
            assert img.getexif().get_ifd(0x8769)[0x9003] == _DATE
