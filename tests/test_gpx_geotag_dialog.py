"""Extra Tools > Library & Metadata > Geotag from GPX Track stamps positions from a recorded track.

``library/gpx_geotag.py`` (GPX parsing and time correlation) was tested but
unreachable. ``match_photos`` correlates a selection, and the dialog loads a
track, matches with the camera's time zone, gap limit and interpolation, and
writes the positions that fall on it.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from PIL import Image

from Imervue.gui import gpx_geotag_dialog as mod
from Imervue.image.gps import extract_gps
from Imervue.library.gpx_geotag import match_photos, parse_gpx

# Two points two minutes apart, in UTC (within the default 120 s gap).
_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
<trkpt lat="25.0000" lon="121.0000"><time>2024-05-06T00:00:00Z</time></trkpt>
<trkpt lat="25.1000" lon="121.2000"><time>2024-05-06T00:02:00Z</time></trkpt>
</trkseg></trk></gpx>"""


def _photo(path, when: str | None, fmt: str = "JPEG"):
    exif = Image.Exif()
    if when is not None:
        exif[0x8769] = {0x9003: when}
    Image.new("RGB", (8, 8), "blue").save(path, fmt, exif=exif)
    return str(path)


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def track_file(tmp_path):
    path = tmp_path / "walk.gpx"
    path.write_text(_GPX, encoding="utf-8")
    return str(path)


def test_match_photos_correlates_each_time_and_skips_untimed():
    track = parse_gpx(_GPX)
    matches = match_photos([("a", datetime(2024, 5, 6, 8, 1)), ("b", None),
                            ("c", datetime(2024, 5, 6, 12, 0))], track, tz_offset_s=8 * 3600)
    (_, mid), (_, untimed), (_, far) = matches
    assert mid == pytest.approx((25.05, 121.1))
    assert untimed is None and far is None


@pytest.fixture
def dialog(qapp, tmp_path):
    paths = [_photo(tmp_path / "mid.jpg", "2024:05:06 08:01:00"),
             _photo(tmp_path / "late.jpg", "2024:05:06 12:00:00"),
             _photo(tmp_path / "none.jpg", None)]
    dlg = mod.GpxGeotagDialog(paths)
    yield dlg, paths
    dlg.deleteLater()


def test_without_a_track_nothing_can_be_written(dialog):
    dlg, _paths = dialog
    assert not dlg._write_btn.isEnabled()  # noqa: SLF001
    assert "Pick a GPX track to match 3 photo(s)" in dlg._summary.text()  # noqa: SLF001


def test_the_time_zone_decides_which_photos_fall_on_the_track(dialog, track_file):
    dlg, paths = dialog
    assert dlg.open_track(track_file) is True
    assert all(coords is None for _, coords in dlg.matches())       # UTC+0: 8 hours off
    assert not dlg._write_btn.isEnabled()  # noqa: SLF001
    dlg._tz.setValue(8.0)  # noqa: SLF001
    matched = dict(dlg.matches())
    assert matched[paths[0]] == pytest.approx((25.05, 121.1))
    assert matched[paths[1]] is None and matched[paths[2]] is None
    assert dlg._summary.text() == ("1 of 3 photo(s) fall on the track (2 points); "  # noqa: SLF001
                                   "1 have no EXIF capture time.")


def test_interpolation_off_takes_the_nearest_point(dialog, track_file):
    dlg, paths = dialog
    dlg.open_track(track_file)
    dlg._tz.setValue(8.0)  # noqa: SLF001
    dlg._gap.setValue(600)  # noqa: SLF001
    dlg._interpolate.setChecked(False)  # noqa: SLF001
    assert dict(dlg.matches())[paths[0]] in ((25.0, 121.0), (25.1, 121.2))


def test_write_stamps_the_matched_photos_only(dialog, track_file):
    dlg, paths = dialog
    dlg.open_track(track_file)
    dlg._tz.setValue(8.0)  # noqa: SLF001
    assert dlg.write() == (1, 0)
    assert extract_gps(paths[0]) == pytest.approx((25.05, 121.1), abs=1e-4)
    assert extract_gps(paths[1]) is None
    assert "Wrote GPS to 1 photo(s); 0 could not" in dlg._summary.text()  # noqa: SLF001


def test_a_match_that_cannot_be_written_is_counted(tmp_path):
    png = _photo(tmp_path / "a.png", "2024:05:06 08:01:00", fmt="PNG")
    assert mod.write_matches([(png, (25.0, 121.0)), ("skipped", None)]) == (0, 1)


@pytest.mark.parametrize("content", [b"<gpx><trk", b"\xff\xfe not utf-8 \x80"])
def test_a_broken_track_is_reported(dialog, tmp_path, content):
    dlg, _paths = dialog
    bad = tmp_path / "bad.gpx"
    bad.write_bytes(content)
    assert dlg.open_track(str(bad)) is False
    assert "Could not read the track" in dlg._summary.text()  # noqa: SLF001
    assert not dlg._write_btn.isEnabled()  # noqa: SLF001


def test_a_missing_track_is_reported(dialog, tmp_path):
    dlg, _paths = dialog
    assert dlg.open_track(str(tmp_path / "gone.gpx")) is False
