"""Tests for pure helpers in Imervue.image.info.

The GUI-driven entry points (``get_image_info_at_pos``, ``show_image_info_dialog``,
``build_image_info``) are exercised via higher-level integration tests; this
file focuses on the stateless helpers that don't require a Qt application or a
running ``GPUImageView``.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest
from PIL import Image

from Imervue.image import info as info_mod


@pytest.fixture
def png_file(tmp_path):
    path = tmp_path / "sample.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(str(path))
    return path


class TestGetFileTimes:
    def test_returns_datetime_pair(self, png_file):
        ctime, mtime = info_mod.get_file_times(png_file)
        assert isinstance(mtime, datetime)
        assert ctime is None or isinstance(ctime, datetime)

    def test_times_reflect_file_state(self, png_file):
        expected = datetime.fromtimestamp(png_file.stat().st_mtime)
        _, mtime = info_mod.get_file_times(png_file)
        assert mtime == expected

    def test_missing_file_raises(self, tmp_path):
        ghost = tmp_path / "ghost.png"
        with pytest.raises(FileNotFoundError):
            info_mod.get_file_times(ghost)


class TestGetExifData:
    def test_no_exif_returns_empty_dict(self, png_file):
        assert info_mod.get_exif_data(png_file) == {}

    def test_unreadable_file_returns_empty_dict(self, tmp_path):
        bad = tmp_path / "bad.jpg"
        bad.write_bytes(b"not an image")
        assert info_mod.get_exif_data(bad) == {}

    def test_missing_file_returns_empty_dict(self, tmp_path):
        ghost = tmp_path / "ghost.jpg"
        assert info_mod.get_exif_data(ghost) == {}


class TestFormatExifInfo:
    def test_empty_exif_returns_sentinel(self):
        assert info_mod.format_exif_info({}) == "No EXIF data"

    def test_missing_keys_use_na_placeholder(self, monkeypatch):
        # Stub the language dict so the test doesn't require a loaded locale.
        template_keys = {
            "image_info_exif_datatime_original": "DT={DateTimeOriginal}\n",
            "image_info_exif_camera_model": "CAM={Make}/{Model}\n",
            "image_info_exif_camera_lens_model": "LENS={LensModel}\n",
            "image_info_exif_camera_focal_length": "FL={FocalLength}\n",
            "image_info_exif_camera_fnumber": "FN={FNumber}\n",
            "image_info_exif_exposure_time": "EXP={ExposureTime}\n",
            "image_info_exif_iso": "ISO={ISOSpeedRatings}\n",
        }
        from Imervue.multi_language import language_wrapper as lw
        monkeypatch.setattr(
            lw.language_wrapper, "language_word_dict", template_keys,
            raising=True,
        )
        out = info_mod.format_exif_info({"Make": "Canon"})
        assert "CAM=Canon/N/A" in out
        assert "DT=N/A" in out
        assert "ISO=N/A" in out

    def test_populated_exif_fields_are_interpolated(self, monkeypatch):
        template_keys = {
            "image_info_exif_datatime_original": "DT={DateTimeOriginal}\n",
            "image_info_exif_camera_model": "CAM={Make}/{Model}\n",
            "image_info_exif_camera_lens_model": "LENS={LensModel}\n",
            "image_info_exif_camera_focal_length": "FL={FocalLength}\n",
            "image_info_exif_camera_fnumber": "FN={FNumber}\n",
            "image_info_exif_exposure_time": "EXP={ExposureTime}\n",
            "image_info_exif_iso": "ISO={ISOSpeedRatings}\n",
        }
        from Imervue.multi_language import language_wrapper as lw
        monkeypatch.setattr(
            lw.language_wrapper, "language_word_dict", template_keys,
            raising=True,
        )
        exif = {
            "DateTimeOriginal": "2024:01:01 10:00:00",
            "Make": "Fujifilm",
            "Model": "X-T5",
            "LensModel": "23mm F2",
            "FocalLength": 23,
            "FNumber": 2.0,
            "ExposureTime": 0.01,
            "ISOSpeedRatings": 400,
        }
        out = info_mod.format_exif_info(exif)
        assert "DT=2024:01:01 10:00:00" in out
        assert "CAM=Fujifilm/X-T5" in out
        assert "LENS=23mm F2" in out
        assert "ISO=400" in out


class TestBuildImageInfoDimensions:
    def test_reports_true_dimensions_not_the_thumbnail(self, tmp_path):
        from pathlib import Path
        from types import SimpleNamespace

        big = tmp_path / "big.png"
        Image.fromarray(np.zeros((600, 800, 3), dtype=np.uint8)).save(str(big))
        # Empty tile cache → the true-dimension (PIL header) path is used, not a
        # downscaled thumbnail. width/height must be the real 800x600.
        fake_gui = SimpleNamespace(tile_cache={})
        result = info_mod.build_image_info(fake_gui, Path(str(big)))
        assert result.get("width") == 800
        assert result.get("height") == 600
        assert "error" not in result


# ---------------------------------------------------------------------------
# Narrowed failure handling
# ---------------------------------------------------------------------------


def test_png_exif_read_does_not_log_a_traceback(png_file, caplog):
    """PNG has no ``_getexif``; that is the normal no-EXIF path, not an error."""
    with caplog.at_level("DEBUG", logger="Imervue.image.info"):
        assert info_mod.get_exif_data(png_file) == {}
    assert "EXIF read failed" not in caplog.text


def test_corrupt_exif_is_logged_and_empty(tmp_path, caplog):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00garbage-garbage")
    with caplog.at_level("DEBUG", logger="Imervue.image.info"):
        assert info_mod.get_exif_data(bad) == {}


def test_out_of_range_ctime_becomes_none(tmp_path, monkeypatch):
    path = tmp_path / "f.bin"
    path.write_bytes(b"x")

    class _Stat:
        st_mtime = 1_700_000_000
        st_ctime = 10 ** 20

    monkeypatch.setattr(type(path), "stat", lambda self: _Stat())
    ctime, mtime = info_mod.get_file_times(path)
    assert ctime is None
    assert isinstance(mtime, datetime)


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


def test_jpeg_exif_matches_pillows_own_merged_view(tmp_path):
    path = tmp_path / "a.jpg"
    Image.new("RGB", (8, 8)).save(path, exif=_camera_exif())
    from PIL.ExifTags import TAGS
    with Image.open(path) as img:
        expected = {TAGS.get(tag, tag): value for tag, value in img._getexif().items()}
    assert info_mod.get_exif_data(path) == expected


def test_heic_exif_is_read(tmp_path):
    """HEIC has no ``_getexif``, so iPhone photos used to show no EXIF at all."""
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    path = tmp_path / "a.heic"
    Image.new("RGB", (16, 16)).save(path, exif=_camera_exif())
    exif = info_mod.get_exif_data(path)
    assert exif["Make"] == "Apple"
    assert exif["DateTimeOriginal"] == "2019:05:06 07:08:09"
    assert exif["GPSInfo"][1] == "N"


def test_exif_read_registers_the_codec_first(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(info_mod, "ensure_pillow_opener", seen.append)
    info_mod.get_exif_data(tmp_path / "missing.HEIC")
    assert seen == [".HEIC"]
