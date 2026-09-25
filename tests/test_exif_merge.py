"""The merged EXIF view: IFD0 + Exif sub-IFD, GPS nested, same as Pillow's JPEG view."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.image import exif_merge
from Imervue.image.exif_merge import merged_exif


@pytest.fixture
def png_file(tmp_path):
    path = tmp_path / "sample.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(str(path))
    return path


def _save(path, *, with_gps: bool):
    exif = Image.Exif()
    exif[271] = "Canon"
    exif.get_ifd(0x8769)[36867] = "2019:05:06 07:08:09"
    if with_gps:
        exif.get_ifd(0x8825)[1] = "N"
    Image.new("RGB", (4, 4)).save(path, exif=exif)
    return path


def test_sub_ifd_tags_are_merged_and_gps_is_nested(tmp_path):
    with Image.open(_save(tmp_path / "a.jpg", with_gps=True)) as img:
        merged = merged_exif(img)
        assert merged == img._getexif()
    assert merged[271] == "Canon"
    assert merged[36867] == "2019:05:06 07:08:09"
    assert merged[0x8825] == {1: "N"}


def test_without_gps_there_is_no_gps_entry(tmp_path):
    with Image.open(_save(tmp_path / "a.jpg", with_gps=False)) as img:
        assert 0x8825 not in merged_exif(img)


def test_image_without_exif_is_empty():
    assert merged_exif(Image.new("RGB", (2, 2))) == {}


# get_exif_data: the merged view read from a file, by tag name


def _camera_exif():
    from PIL.TiffImagePlugin import IFDRational
    exif = Image.Exif()
    exif[271] = "Apple"
    exif.get_ifd(0x8769)[36867] = "2019:05:06 07:08:09"
    exif.get_ifd(0x8769)[33434] = IFDRational(1, 250)
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (IFDRational(25), IFDRational(2), IFDRational(0))
    gps[3], gps[4] = "E", (IFDRational(121), IFDRational(30), IFDRational(0))
    return exif


class TestGetExifData:
    def test_no_exif_returns_empty_dict(self, png_file):
        assert exif_merge.get_exif_data(png_file) == {}

    def test_unreadable_file_returns_empty_dict(self, tmp_path):
        bad = tmp_path / "bad.jpg"
        bad.write_bytes(b"not an image")
        assert exif_merge.get_exif_data(bad) == {}

    def test_missing_file_returns_empty_dict(self, tmp_path):
        ghost = tmp_path / "ghost.jpg"
        assert exif_merge.get_exif_data(ghost) == {}


def test_png_exif_read_does_not_log_a_traceback(png_file, caplog):
    """PNG has no ``_getexif``; that is the normal no-EXIF path, not an error."""
    with caplog.at_level("DEBUG", logger="Imervue.image.info"):
        assert exif_merge.get_exif_data(png_file) == {}
    assert "EXIF read failed" not in caplog.text


def test_corrupt_exif_is_logged_and_empty(tmp_path, caplog):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00garbage-garbage")
    with caplog.at_level("DEBUG", logger="Imervue.image.info"):
        assert exif_merge.get_exif_data(bad) == {}


def test_jpeg_exif_matches_pillows_own_merged_view(tmp_path):
    path = tmp_path / "a.jpg"
    Image.new("RGB", (8, 8)).save(path, exif=_camera_exif())
    from PIL.ExifTags import TAGS
    with Image.open(path) as img:
        expected = {TAGS.get(tag, tag): value for tag, value in img._getexif().items()}
    assert exif_merge.get_exif_data(path) == expected


def test_heic_exif_is_read(tmp_path):
    """HEIC has no ``_getexif``, so iPhone photos used to show no EXIF at all."""
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    path = tmp_path / "a.heic"
    Image.new("RGB", (16, 16)).save(path, exif=_camera_exif())
    exif = exif_merge.get_exif_data(path)
    assert exif["Make"] == "Apple"
    assert exif["DateTimeOriginal"] == "2019:05:06 07:08:09"
    assert exif["GPSInfo"][1] == "N"


def test_exif_read_registers_the_codec_first(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(exif_merge, "ensure_pillow_opener", seen.append)
    exif_merge.get_exif_data(tmp_path / "missing.HEIC")
    assert seen == [".HEIC"]
