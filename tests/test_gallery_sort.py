"""Tests for the web-gallery sort / filter / group helpers."""
from __future__ import annotations

import datetime as _dt
import os

import pytest

from Imervue.export.gallery_sort import (
    filter_images,
    group_images,
    sort_images,
)


# ---------------------------------------------------------------------------
# sort_images
# ---------------------------------------------------------------------------


def test_sort_by_name():
    paths = ["/x/Banana.png", "/x/apple.png", "/x/cherry.png"]
    assert sort_images(paths, "name") == [
        "/x/apple.png", "/x/Banana.png", "/x/cherry.png"]


def test_sort_by_name_reverse():
    assert sort_images(["/a.png", "/b.png"], "name", reverse=True) == [
        "/b.png", "/a.png"]


def test_sort_by_size(tmp_path):
    small = tmp_path / "small.bin"
    big = tmp_path / "big.bin"
    small.write_bytes(b"x" * 10)
    big.write_bytes(b"x" * 5000)
    assert sort_images([str(big), str(small)], "size") == [str(small), str(big)]


def test_sort_by_mtime(tmp_path):
    old = tmp_path / "old.bin"
    new = tmp_path / "new.bin"
    old.write_bytes(b"o")
    new.write_bytes(b"n")
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))
    assert sort_images([str(new), str(old)], "mtime") == [str(old), str(new)]


def test_sort_missing_file_does_not_raise():
    # Unreadable files sort as zero-stat rather than erroring.
    assert sort_images(["/no/such.png"], "size") == ["/no/such.png"]


def test_sort_unknown_order_raises():
    with pytest.raises(ValueError, match="unknown sort order"):
        sort_images(["/a.png"], "rainbow")


# ---------------------------------------------------------------------------
# filter_images
# ---------------------------------------------------------------------------


def test_filter_glob_case_insensitive():
    paths = ["/a/IMG_1.PNG", "/a/IMG_2.jpg", "/a/snap.png"]
    assert filter_images(paths, "img_*.png") == ["/a/IMG_1.PNG"]


def test_filter_empty_pattern_keeps_all():
    paths = ["/a.png", "/b.jpg"]
    assert filter_images(paths, "") == paths


# ---------------------------------------------------------------------------
# group_images
# ---------------------------------------------------------------------------


def test_group_by_extension():
    paths = ["/a/x.png", "/a/y.PNG", "/a/z.jpg", "/a/noext"]
    groups = group_images(paths, "ext")
    assert groups["png"] == ["/a/x.png", "/a/y.PNG"]
    assert groups["jpg"] == ["/a/z.jpg"]
    assert groups["(no extension)"] == ["/a/noext"]


def test_group_by_parent_folder():
    groups = group_images(["/trip/a.png", "/home/b.png", "/trip/c.png"], "parent")
    assert groups["trip"] == ["/trip/a.png", "/trip/c.png"]
    assert groups["home"] == ["/home/b.png"]


def test_group_by_date(tmp_path):
    p = tmp_path / "a.png"
    p.write_bytes(b"x")
    ts = _dt.datetime(2024, 5, 1, 12, 0).timestamp()
    os.utime(p, (ts, ts))
    groups = group_images([str(p)], "date")
    assert groups["2024-05-01"] == [str(p)]


def test_group_unknown_key_raises():
    with pytest.raises(ValueError, match="unknown group key"):
        group_images(["/a.png"], "colour")
