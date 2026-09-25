"""Tests for ``sort_menu``'s resolution sort key."""
from __future__ import annotations

import pytest
from PIL import Image

from Imervue.menu import sort_menu


def test_resolution_is_pixel_count(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGB", (6, 4)).save(path)
    assert sort_menu._sort_key_resolution(str(path)) == 24  # noqa: SLF001


def test_unreadable_files_sort_as_zero(tmp_path, monkeypatch):
    text = tmp_path / "notes.png"
    text.write_text("not an image", encoding="utf-8")
    big = tmp_path / "big.png"
    Image.new("RGB", (32, 32)).save(big)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    for path in (tmp_path / "absent.png", text, big):
        assert sort_menu._sort_key_resolution(str(path)) == 0, path.name  # noqa: SLF001


def test_unexpected_errors_propagate(monkeypatch):
    def boom(_path):
        raise RuntimeError("bug")

    monkeypatch.setattr(Image, "open", boom)
    with pytest.raises(RuntimeError):
        sort_menu._sort_key_resolution("x.png")  # noqa: SLF001


def test_a_camera_raw_sorts_by_its_developed_size(tmp_path, monkeypatch):
    """Pillow reads a RAW's embedded preview: a 24 MP shot sorted as 15 pixels."""
    from Imervue.image import dimensions
    raw = tmp_path / "shot.cr2"
    Image.new("RGB", (5, 3)).save(raw, format="TIFF")          # all Pillow sees
    monkeypatch.setattr(dimensions, "raw_dimensions", lambda _path: (6000, 4000))
    assert sort_menu._sort_key_resolution(str(raw)) == 24_000_000  # noqa: SLF001


def test_a_quarter_turned_photo_keeps_its_pixel_count(tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    assert sort_menu._sort_key_resolution(str(path)) == 800  # noqa: SLF001


def test_sorting_by_name_puts_img2_before_img10():
    """A plain string sort went img1, img10, img2 - unlike the file tree and Explorer."""
    paths = ["/p/IMG10.jpg", "/p/img2.jpg", "/p/img1.jpg"]
    assert sorted(paths, key=sort_menu._sort_key_name) == [  # noqa: SLF001
        "/p/img1.jpg", "/p/img2.jpg", "/p/IMG10.jpg"]


def test_created_is_the_creation_time(tmp_path):
    import os
    path = tmp_path / "a.png"
    path.write_bytes(b"x")
    st = os.stat(path)
    expected = getattr(st, "st_birthtime", st.st_ctime)
    assert sort_menu._sort_key_created(str(path)) == pytest.approx(expected)  # noqa: SLF001
    assert sort_menu._sort_key_created(str(tmp_path / "gone.png")) == 0  # noqa: SLF001
