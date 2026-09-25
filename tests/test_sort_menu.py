"""Tests for ``sort_menu``: its sort keys and its menu."""
from __future__ import annotations

from pathlib import Path

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



def _shot(path, taken: str | None, mtime: float):
    """A JPEG taken at *taken* (EXIF DateTimeOriginal), last modified at *mtime*."""
    import os
    exif = Image.Exif()
    if taken is not None:
        exif.get_ifd(0x8769)[0x9003] = taken
    Image.new("RGB", (4, 4)).save(path, exif=exif)
    os.utime(path, (mtime, mtime))
    return str(path)


def test_date_taken_follows_the_camera_not_the_file(tmp_path):
    """A photo copied or edited later has a newer file date than when it was taken."""
    early = _shot(tmp_path / "b.jpg", "2024:05:01 09:00:00", mtime=2_000_000_000)
    late = _shot(tmp_path / "a.jpg", "2024:05:02 09:00:00", mtime=1_000_000_000)
    assert sorted([late, early], key=sort_menu._sort_key_taken) == [early, late]  # noqa: SLF001
    assert sorted([late, early], key=sort_menu._sort_key_modified) == [late, early]  # noqa: SLF001


def test_a_picture_without_a_date_taken_sorts_by_its_modified_time(tmp_path):
    import datetime as dt
    stamp = dt.datetime(2024, 5, 1, 12, 0).timestamp()
    screenshot = _shot(tmp_path / "screenshot.jpg", None, mtime=stamp)
    photo = _shot(tmp_path / "photo.jpg", "2024:05:01 10:00:00", mtime=stamp + 99_999)
    assert sorted([screenshot, photo], key=sort_menu._sort_key_taken) == [photo, screenshot]  # noqa: SLF001


def test_a_burst_within_one_second_keeps_its_name_order(tmp_path):
    shots = [_shot(tmp_path / f"IMG_{n}.jpg", "2024:05:01 09:00:00", mtime=1_000_000_000 - n)
             for n in (10, 2, 1)]
    assert [Path(p).name for p in sorted(shots, key=sort_menu._sort_key_taken)] == [  # noqa: SLF001
        "IMG_1.jpg", "IMG_2.jpg", "IMG_10.jpg"]


def test_a_missing_file_sorts_first(tmp_path):
    present = _shot(tmp_path / "a.jpg", "2024:05:01 09:00:00", mtime=1_000_000_000)
    gone = str(tmp_path / "gone.jpg")
    assert sorted([present, gone], key=sort_menu._sort_key_taken) == [gone, present]  # noqa: SLF001


def test_the_sort_menu_offers_date_taken(qapp):
    from PySide6.QtWidgets import QMainWindow

    from Imervue.multi_language.language_wrapper import language_wrapper
    window = QMainWindow()
    try:
        menu = sort_menu.build_sort_menu(window)
        texts = [action.text() for action in menu.actions()]
    finally:
        window.deleteLater()
    assert language_wrapper.language_word_dict["sort_by_taken"] in texts
