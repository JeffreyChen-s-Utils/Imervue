"""Tests for pure helpers in Imervue.image.info.

The GUI-driven entry points (``get_image_info_at_pos``, ``show_image_info_dialog``,
``build_image_info``) are exercised via higher-level integration tests; this
file focuses on the stateless helpers that don't require a Qt application or a
running ``GPUImageView``.
"""
from __future__ import annotations

import sys
import types
from datetime import datetime

import numpy as np
import pytest
from PIL import Image


# ``Imervue.image.info`` pulls in ``image_loader``, which imports the optional
# ``rawpy`` dependency (only needed for CR2/NEF/ARW/etc. RAW support). Stub it
# out so this test file can exercise the pure helpers without forcing rawpy on
# the CI/dev environment.
if "rawpy" not in sys.modules:
    sys.modules["rawpy"] = types.ModuleType("rawpy")

from Imervue.image import info as info_mod  # noqa: E402


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
