"""Tests for GPX track-log geotagging."""
from __future__ import annotations

from datetime import datetime

import pytest

from Imervue.library.gpx_geotag import correlate, parse_gpx

_NS = 'xmlns="http://www.topografix.com/GPX/1/1"'


def _gpx(points):
    body = "".join(
        f'<trkpt lat="{lat}" lon="{lon}"><time>{t}</time></trkpt>'
        for t, lat, lon in points
    )
    return f'<?xml version="1.0"?><gpx version="1.1" {_NS}><trk><trkseg>{body}</trkseg></trk></gpx>'


_TRACK = [
    ("2024-01-01T12:00:00Z", 10.0, 20.0),
    ("2024-01-01T12:01:00Z", 11.0, 22.0),
]


# ---------------------------------------------------------------------------
# parse_gpx
# ---------------------------------------------------------------------------


def test_parse_reads_namespaced_trackpoints():
    track = parse_gpx(_gpx(_TRACK))
    assert len(track) == 2
    assert track[0] == (datetime(2024, 1, 1, 12, 0, 0), 10.0, 20.0)


def test_parse_sorts_by_time():
    out_of_order = [_TRACK[1], _TRACK[0]]
    track = parse_gpx(_gpx(out_of_order))
    assert [t for t, _, _ in track] == sorted(t for t, _, _ in track)


def test_parse_skips_trkpt_without_time():
    xml = (f'<gpx {_NS}><trk><trkseg>'
           '<trkpt lat="1" lon="2"></trkpt>'
           '<trkpt lat="3" lon="4"><time>2024-01-01T00:00:00Z</time></trkpt>'
           '</trkseg></trk></gpx>')
    assert len(parse_gpx(xml)) == 1


def test_parse_empty_track():
    assert parse_gpx(f'<gpx {_NS}></gpx>') == []


def test_parse_normalises_timezone_offset():
    # 12:30+01:00 is 11:30 UTC.
    xml = _gpx([("2024-01-01T12:30:00+01:00", 5.0, 6.0)])
    assert parse_gpx(xml)[0][0] == datetime(2024, 1, 1, 11, 30, 0)


def test_parse_malformed_raises():
    with pytest.raises(ValueError, match="invalid GPX"):
        parse_gpx("<gpx><trk>")


# ---------------------------------------------------------------------------
# correlate
# ---------------------------------------------------------------------------


def test_correlate_exact_match():
    track = parse_gpx(_gpx(_TRACK))
    assert correlate(datetime(2024, 1, 1, 12, 0, 0), track) == (10.0, 20.0)


def test_correlate_interpolates_midpoint():
    track = parse_gpx(_gpx(_TRACK))
    lat, lon = correlate(datetime(2024, 1, 1, 12, 0, 30), track)
    assert lat == pytest.approx(10.5)
    assert lon == pytest.approx(21.0)


def test_correlate_gap_too_large_returns_none():
    wide = [("2024-01-01T12:00:00Z", 10.0, 20.0), ("2024-01-01T12:10:00Z", 11.0, 22.0)]
    track = parse_gpx(_gpx(wide))
    assert correlate(datetime(2024, 1, 1, 12, 5, 0), track, max_gap_s=120) is None


def test_correlate_nearest_when_not_interpolating():
    track = parse_gpx(_gpx(_TRACK))
    # 12:00:20 is closest to the 12:00 point.
    assert correlate(
        datetime(2024, 1, 1, 12, 0, 20), track, interpolate=False,
    ) == (10.0, 20.0)


def test_correlate_outside_range_within_gap():
    track = parse_gpx(_gpx(_TRACK))
    assert correlate(datetime(2024, 1, 1, 11, 59, 0), track, max_gap_s=120) == (10.0, 20.0)


def test_correlate_outside_range_beyond_gap():
    track = parse_gpx(_gpx(_TRACK))
    assert correlate(datetime(2024, 1, 1, 11, 0, 0), track) is None


def test_correlate_applies_timezone_offset():
    track = parse_gpx(_gpx(_TRACK))
    # Camera local 20:00:30 at UTC+8 -> 12:00:30 UTC -> interpolated midpoint.
    lat, lon = correlate(
        datetime(2024, 1, 1, 20, 0, 30), track, tz_offset_s=28800,
    )
    assert (lat, lon) == (pytest.approx(10.5), pytest.approx(21.0))


def test_correlate_empty_track():
    assert correlate(datetime(2024, 1, 1, 12, 0, 0), []) is None


def test_correlate_boundary_just_inside_gap():
    track = parse_gpx(_gpx(_TRACK))
    inside = correlate(datetime(2024, 1, 1, 11, 58, 0), track, max_gap_s=120)
    outside = correlate(datetime(2024, 1, 1, 11, 57, 59), track, max_gap_s=120)
    assert inside == (10.0, 20.0)
    assert outside is None
