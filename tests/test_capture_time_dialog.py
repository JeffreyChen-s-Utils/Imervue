"""Extra Tools > Library & Metadata > Edit Capture Time shifts the EXIF capture time of a selection.

``library/capture_time.py`` (shift arithmetic, EXIF rewrite plan) was tested but
unreachable. It gained the EXIF read / write of one photo, and the dialog drives
it: a shift typed in, or the first photo's true time, moves every photo alike.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PIL import Image
from PySide6.QtCore import QDateTime

from Imervue.gui import capture_time_dialog as mod
from Imervue.library.capture_time import exif_capture_time, write_capture_time


def _photo(path, when: str | None = "2024:05:06 07:08:09", fmt: str = "JPEG"):
    exif = Image.Exif()
    if when is not None:
        exif[0x8769] = {0x9003: when}
    Image.new("RGB", (8, 8), "red").save(path, fmt, exif=exif)
    return str(path)


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def test_the_writer_sets_all_three_dates_and_keeps_the_pixels(tmp_path):
    path = _photo(tmp_path / "a.jpg")
    with Image.open(path) as img:
        before = img.tobytes()
    assert write_capture_time(path, "2025:01:02 03:04:05") is True
    assert exif_capture_time(path) == datetime(2025, 1, 2, 3, 4, 5)
    with Image.open(path) as img:
        exif = img.getexif()
        sub = exif.get_ifd(0x8769)
        assert img.tobytes() == before
    assert exif[0x0132] == sub[0x9003] == sub[0x9004] == "2025:01:02 03:04:05"


def test_the_writer_refuses_what_it_cannot_rewrite(tmp_path):
    png = tmp_path / "a.png"
    Image.new("RGB", (4, 4)).save(png)
    assert write_capture_time(png, "2025:01:02 03:04:05") is False
    assert write_capture_time(tmp_path / "missing.jpg", "2025:01:02 03:04:05") is False


def test_a_photo_without_an_exif_date_has_no_capture_time(tmp_path):
    assert exif_capture_time(_photo(tmp_path / "a.jpg", None)) is None


@pytest.mark.parametrize(("delta", "parts"), [
    (timedelta(hours=-1, minutes=-30), (0, -1, -30, 0)),
    (timedelta(days=2, seconds=61), (2, 0, 1, 1)),
    (timedelta(0), (0, 0, 0, 0)),
])
def test_split_delta_keeps_the_sign_on_every_part(delta, parts):
    assert mod.split_delta(delta) == parts


@pytest.fixture
def dialog(qapp, tmp_path):
    paths = [_photo(tmp_path / "a.jpg"), _photo(tmp_path / "b.jpg", "2024:05:06 09:00:00"),
             _photo(tmp_path / "c.jpg", None)]
    dlg = mod.CaptureTimeDialog(paths)
    yield dlg, paths
    dlg.deleteLater()


def test_only_photos_with_a_capture_time_are_listed(dialog):
    dlg, paths = dialog
    assert [p for p, _ in dlg._items] == paths[:2]  # noqa: SLF001
    assert dlg._apply_btn.isEnabled()  # noqa: SLF001


def test_typing_a_shift_moves_the_reference_and_the_preview(dialog):
    dlg, _paths = dialog
    dlg._hours.setValue(-2)  # noqa: SLF001
    assert dlg.delta() == timedelta(hours=-2)
    assert dlg._reference.dateTime().toPython() == datetime(2024, 5, 6, 5, 8, 9)  # noqa: SLF001
    assert dlg._preview.text() == "a.jpg: 2024-05-06 07:08:09 → 2024-05-06 05:08:09"  # noqa: SLF001


def test_naming_the_true_time_fills_in_the_shift(dialog):
    dlg, _paths = dialog
    dlg._reference.setDateTime(QDateTime(datetime(2024, 5, 7, 8, 9, 10)))  # noqa: SLF001
    assert dlg.delta() == timedelta(days=1, hours=1, minutes=1, seconds=1)
    assert (dlg._days.value(), dlg._seconds.value()) == (1, 1)  # noqa: SLF001


def test_apply_rewrites_every_photo_and_resets_the_shift(dialog):
    dlg, paths = dialog
    dlg._days.setValue(-1)  # noqa: SLF001
    assert dlg.apply() == (2, 0)
    assert exif_capture_time(paths[0]) == datetime(2024, 5, 5, 7, 8, 9)
    assert exif_capture_time(paths[1]) == datetime(2024, 5, 5, 9, 0, 0)
    assert exif_capture_time(paths[2]) is None
    assert dlg.delta() == timedelta(0)
    assert "Rewrote 2 photo(s); 0 could not" in dlg._status.text()  # noqa: SLF001


def test_a_shift_off_the_calendar_writes_nothing(qapp, tmp_path):
    path = _photo(tmp_path / "a.jpg", "0001:01:02 00:00:00")
    dlg = mod.CaptureTimeDialog([path])
    try:
        dlg._days.setValue(-36500)  # noqa: SLF001
        assert dlg.apply() == (0, 0)
        assert "outside the calendar" in dlg._status.text()  # noqa: SLF001
        assert exif_capture_time(path) == datetime(1, 1, 2)
    finally:
        dlg.deleteLater()


def test_a_format_that_cannot_be_rewritten_is_counted(qapp, tmp_path):
    png = _photo(tmp_path / "a.png", fmt="PNG")          # dated, but its EXIF can't be rewritten
    items = mod.read_capture_times([png])
    assert len(items) == 1
    assert mod.apply_shift(items, timedelta(hours=1)) == (0, 1)


def test_no_dated_photos_leaves_apply_off(qapp, tmp_path):
    dlg = mod.CaptureTimeDialog([_photo(tmp_path / "a.jpg", None)])
    try:
        assert not dlg._apply_btn.isEnabled()  # noqa: SLF001
        assert dlg._preview.text() == ""  # noqa: SLF001
    finally:
        dlg.deleteLater()
