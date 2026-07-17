"""Tests for EXIF-date import (date parsing + path planning)."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

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


def test_plan_import_avoids_existing_on_disk_file(tmp_path):
    """Regression: planning only de-duped within the batch, so a file
    whose name already existed in the target folder was silently
    overwritten. An on-disk collision must also get a ``_N`` suffix."""
    existing_dir = tmp_path / "2024" / "07"
    existing_dir.mkdir(parents=True)
    (existing_dir / "x.jpg").write_bytes(b"old")   # pre-existing photo

    items = [("/somewhere/x.jpg", datetime(2024, 7, 15))]
    dests = [d for _src, d in plan_import(items, str(tmp_path))]
    assert Path(dests[0]).name == "x_1.jpg"        # did not target x.jpg


def test_import_by_date_does_not_overwrite_existing(tmp_path):
    src = tmp_path / "photo.jpg"
    src.write_bytes(b"new")
    when = datetime(2022, 3, 9, 10, 0, 0)
    os.utime(src, (when.timestamp(), when.timestamp()))
    dest_root = tmp_path / "out"
    target_dir = dest_root / "2022" / "03"
    target_dir.mkdir(parents=True)
    (target_dir / "photo.jpg").write_bytes(b"original")   # must survive

    count = import_by_date([str(src)], str(dest_root))
    assert count == 1
    assert (target_dir / "photo.jpg").read_bytes() == b"original"
    assert (target_dir / "photo_1.jpg").read_bytes() == b"new"


def test_import_by_date_skips_failures_and_continues(tmp_path, monkeypatch):
    """A copy that raises mid-batch (locked file / full disk) must be
    skipped, not abort the whole import."""
    import Imervue.library.date_import as di

    when = datetime(2022, 3, 9, 10, 0, 0)
    first = tmp_path / "a_first.jpg"
    second = tmp_path / "b_second.jpg"
    for f in (first, second):
        f.write_bytes(b"\x00")
        os.utime(f, (when.timestamp(), when.timestamp()))
    dest_root = tmp_path / "out"

    real_copy = di.shutil.copy2
    calls = {"n": 0}

    def flaky_copy(src, dst, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("simulated locked file")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(di.shutil, "copy2", flaky_copy)
    count = import_by_date([str(first), str(second)], str(dest_root))
    assert count == 1   # the second file still landed despite the first failing
    assert (dest_root / "2022" / "03" / "b_second.jpg").exists()
    assert not (dest_root / "2022" / "03" / "a_first.jpg").exists()


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
