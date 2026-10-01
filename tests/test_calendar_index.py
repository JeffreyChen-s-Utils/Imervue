"""Tests for calendar-by-date bucketing."""
from __future__ import annotations

import datetime as _dt
import os

import numpy as np
import pytest
from PIL import Image

piexif = pytest.importorskip("piexif")

from Imervue.library import calendar_index as ci  # noqa: E402  # piexif gate above


def _write_jpeg_with_date(path, date_str: str | None):
    exif_bytes = b""
    if date_str:
        exif_bytes = piexif.dump({
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: date_str.encode(),
            }
        })
    arr = np.zeros((8, 8, 3), dtype=np.uint8)
    Image.fromarray(arr).save(str(path), format="JPEG", exif=exif_bytes)


class TestCaptureDate:
    def test_uses_exif_when_available(self, tmp_path):
        p = tmp_path / "a.jpg"
        _write_jpeg_with_date(p, "2024:07:15 12:00:00")
        assert ci.capture_date(str(p)) == _dt.date(2024, 7, 15)

    def test_falls_back_to_mtime(self, tmp_path):
        p = tmp_path / "b.jpg"
        _write_jpeg_with_date(p, None)
        past = _dt.datetime(2020, 3, 10, 9, 0, 0).timestamp()
        os.utime(p, (past, past))
        assert ci.capture_date(str(p)) == _dt.date(2020, 3, 10)

    def test_missing_file_returns_unknown(self, tmp_path):
        assert ci.capture_date(str(tmp_path / "nope.jpg")) == ci.UNKNOWN_DATE


class TestGrouping:
    def test_group_by_date_buckets_same_day(self, tmp_path):
        p1 = tmp_path / "a.jpg"
        p2 = tmp_path / "b.jpg"
        _write_jpeg_with_date(p1, "2024:07:15 10:00:00")
        _write_jpeg_with_date(p2, "2024:07:15 15:30:00")
        grouped = ci.group_by_date([str(p1), str(p2)])
        assert len(grouped[_dt.date(2024, 7, 15)]) == 2

    def test_group_by_month_aggregates(self, tmp_path):
        p1 = tmp_path / "a.jpg"
        p2 = tmp_path / "b.jpg"
        _write_jpeg_with_date(p1, "2024:07:01 10:00:00")
        _write_jpeg_with_date(p2, "2024:07:31 15:30:00")
        grouped = ci.group_by_month([str(p1), str(p2)])
        assert len(grouped[(2024, 7)]) == 2

    def test_date_histogram_counts(self, tmp_path):
        files = []
        for i in range(3):
            p = tmp_path / f"img{i}.jpg"
            _write_jpeg_with_date(p, "2024:01:05 12:00:00")
            files.append(str(p))
        hist = ci.date_histogram(files)
        assert hist[_dt.date(2024, 1, 5)] == 3


class TestCaptureDatetime:
    def test_keeps_exif_time(self, tmp_path):
        p = tmp_path / "a.jpg"
        _write_jpeg_with_date(p, "2024:07:15 14:30:45")
        assert ci.capture_datetime(str(p)) == _dt.datetime(2024, 7, 15, 14, 30, 45)

    def test_mtime_fallback_keeps_hour(self, tmp_path):
        p = tmp_path / "b.jpg"
        _write_jpeg_with_date(p, None)
        past = _dt.datetime(2020, 3, 10, 9, 0, 0).timestamp()
        os.utime(p, (past, past))
        assert ci.capture_datetime(str(p)).hour == 9

    def test_missing_returns_unknown_datetime(self, tmp_path):
        assert ci.capture_datetime(str(tmp_path / "no.jpg")) == ci.UNKNOWN_DATETIME


class TestHourGrouping:
    def test_group_by_hour_buckets_same_hour(self, monkeypatch):
        times = {
            "a": _dt.datetime(2024, 1, 1, 9, 15),
            "b": _dt.datetime(2024, 1, 1, 9, 45),
            "c": _dt.datetime(2024, 1, 1, 14, 0),
        }
        monkeypatch.setattr(ci, "capture_datetime", lambda p: times[str(p)])
        groups = ci.group_by_hour(["a", "b", "c"])
        assert groups[_dt.datetime(2024, 1, 1, 9, 0)] == ["a", "b"]
        assert groups[_dt.datetime(2024, 1, 1, 14, 0)] == ["c"]

    def test_hour_histogram_counts_hour_of_day(self, monkeypatch):
        times = {
            "a": _dt.datetime(2024, 1, 1, 9, 0),
            "b": _dt.datetime(2024, 3, 5, 9, 30),   # same hour, different day
            "c": _dt.datetime(2024, 1, 1, 18, 0),
        }
        monkeypatch.setattr(ci, "capture_datetime", lambda p: times[str(p)])
        assert ci.hour_histogram(["a", "b", "c"]) == {9: 2, 18: 1}

    def test_group_by_hour_unknown_bucket(self, monkeypatch):
        monkeypatch.setattr(ci, "capture_datetime", lambda p: ci.UNKNOWN_DATETIME)
        assert ci.group_by_hour(["x"]) == {ci.UNKNOWN_DATETIME: ["x"]}

    def test_hour_histogram_skips_unknown(self, monkeypatch):
        monkeypatch.setattr(ci, "capture_datetime", lambda p: ci.UNKNOWN_DATETIME)
        assert ci.hour_histogram(["x"]) == {}


def test_corrupt_webp_exif_falls_back_to_mtime(tmp_path):
    from test_read_errors import corrupt_exif_webp

    p = tmp_path / "bad.webp"
    p.write_bytes(corrupt_exif_webp())
    stamp = _dt.datetime(2016, 3, 4, 5, 6, 7).timestamp()
    os.utime(p, (stamp, stamp))
    assert ci.capture_datetime(str(p)) == _dt.datetime(2016, 3, 4, 5, 6, 7)


def test_dashed_exif_datetime_is_read(tmp_path):
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = "2020-01-02 03:04:05"
    path = tmp_path / "a.jpg"
    Image.new("RGB", (4, 4)).save(path, exif=exif)
    assert ci.capture_datetime(str(path)) == _dt.datetime(2020, 1, 2, 3, 4, 5)


def test_heic_capture_time_is_read(tmp_path):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = "2018:09:10 11:12:13"
    path = tmp_path / "a.heic"
    Image.new("RGB", (16, 16)).save(path, exif=exif)
    assert ci.capture_datetime(str(path)) == _dt.datetime(2018, 9, 10, 11, 12, 13)


def test_codec_is_registered_before_reading(tmp_path, monkeypatch):
    seen = []
    from Imervue.image import exif_merge
    monkeypatch.setattr(exif_merge, "ensure_pillow_opener", seen.append)
    ci.capture_datetime(str(tmp_path / "missing.jxl"))
    assert seen == [".jxl"]
