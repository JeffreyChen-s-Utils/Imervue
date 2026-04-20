"""Tests for calendar-by-date bucketing."""
from __future__ import annotations

import datetime as _dt
import os

import numpy as np
import pytest
from PIL import Image

piexif = pytest.importorskip("piexif")

from Imervue.library import calendar_index as ci


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
