"""Tests for EXIF-date import (date parsing + path planning)."""
from __future__ import annotations

import os
from datetime import datetime

from Imervue.library.date_import import (
    dated_folder,
    import_by_date,
    parse_exif_datetime,
    plan_import,
)


def test_dated_folder_default_pattern():
    assert dated_folder(datetime(2024, 7, 15, 12, 0, 0)) == "2024/07"


def test_parse_exif_datetime_valid():
    assert parse_exif_datetime("2024:07:15 12:30:00") == datetime(2024, 7, 15, 12, 30, 0)


def test_parse_exif_datetime_invalid():
    assert parse_exif_datetime("") is None
    assert parse_exif_datetime("garbage") is None
    assert parse_exif_datetime(None) is None


def test_plan_import_routes_by_month():
    items = [("/a/x.jpg", datetime(2024, 7, 15)), ("/b/y.jpg", datetime(2024, 8, 1))]
    plan = dict(plan_import(items, "/out"))
    assert plan["/a/x.jpg"].replace("\\", "/") == "/out/2024/07/x.jpg"
    assert plan["/b/y.jpg"].replace("\\", "/") == "/out/2024/08/y.jpg"


def test_plan_import_resolves_in_batch_collisions():
    items = [("/a/x.jpg", datetime(2024, 7, 15)), ("/b/x.jpg", datetime(2024, 7, 20))]
    dests = [d.replace("\\", "/") for _src, d in plan_import(items, "/out")]
    assert dests == ["/out/2024/07/x.jpg", "/out/2024/07/x_1.jpg"]


def test_import_by_date_copies_into_dated_folder(tmp_path):
    src = tmp_path / "photo.jpg"
    src.write_bytes(b"\x00")
    # Force a known mtime (no EXIF on this stub) → routes by that date.
    when = datetime(2022, 3, 9, 10, 0, 0)
    os.utime(src, (when.timestamp(), when.timestamp()))
    dest_root = tmp_path / "out"
    count = import_by_date([str(src)], str(dest_root))
    assert count == 1
    assert (dest_root / "2022" / "03" / "photo.jpg").exists()
