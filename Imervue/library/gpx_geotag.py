"""GPX track-log geotagging — derive coordinates from a recorded track.

The standard "I carried a GPS logger, now stamp my photos" workflow (digiKam's
*Geolocation* correlator, ``gpscorrelate``): parse a GPX track, then for each
photo's capture time look up where the track says you were. Times that fall
between two trackpoints are linearly interpolated; gaps wider than a threshold
return nothing rather than a guess.

Parsing goes through :mod:`defusedxml` (untrusted XML). The result feeds the
existing ``image.gps_geotag`` writer. Pure stdlib + defusedxml — ships in main.
"""
from __future__ import annotations

import bisect
from datetime import datetime, timedelta

from defusedxml import ElementTree as ET  # noqa: N817  # defused stdlib alias

_DEFAULT_MAX_GAP_S = 120
TrackPoint = tuple[datetime, float, float]


def parse_gpx(xml_text: str) -> list[TrackPoint]:
    """Parse GPX *xml_text* into a time-sorted list of ``(utc_time, lat, lon)``.

    Track point times are returned as naive UTC ``datetime`` (the GPX ``Z``
    suffix is normalised away). Points without a ``<time>`` are skipped. Raises
    ``ValueError`` if the XML is malformed.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as err:
        raise ValueError(f"invalid GPX: {err}") from err
    points = [p for p in (_read_trkpt(el) for el in _iter_local(root, "trkpt"))
              if p is not None]
    points.sort(key=lambda p: p[0])
    return points


def correlate(
    when: datetime,
    track: list[TrackPoint],
    *,
    max_gap_s: int = _DEFAULT_MAX_GAP_S,
    interpolate: bool = True,
    tz_offset_s: int = 0,
) -> tuple[float, float] | None:
    """Return the ``(lat, lon)`` for capture time *when*, or ``None``.

    *when* is the camera's local time; *tz_offset_s* is how far that runs ahead
    of UTC (e.g. ``28800`` for UTC+8). A point is returned only if a trackpoint
    (or an interpolatable pair) lies within *max_gap_s* seconds of the corrected
    time; otherwise ``None``. With *interpolate* off the nearest point is used.
    """
    if not track:
        return None
    target = when - timedelta(seconds=tz_offset_s)
    times = [t for t, _, _ in track]
    pos = bisect.bisect_left(times, target)
    if pos < len(times) and times[pos] == target:
        return track[pos][1], track[pos][2]
    if pos == 0 or pos == len(times):
        return _nearest_endpoint(track[0] if pos == 0 else track[-1], target, max_gap_s)
    before, after = track[pos - 1], track[pos]
    if interpolate:
        return _interpolate(before, after, target, max_gap_s)
    return _nearest_in_segment(before, after, target, max_gap_s)


def _read_trkpt(element) -> TrackPoint | None:
    lat, lon = element.get("lat"), element.get("lon")
    time_el = next(iter(_iter_local(element, "time")), None)
    if lat is None or lon is None or time_el is None or not time_el.text:
        return None
    return _parse_time(time_el.text), float(lat), float(lon)


def _parse_time(raw: str) -> datetime:
    text = raw.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.replace(tzinfo=None) - _utc_shift(parsed)


def _utc_shift(parsed: datetime) -> timedelta:
    return parsed.utcoffset() or timedelta(0)


def _iter_local(element, name: str):
    """Yield descendants (and self) whose tag local-name equals *name*."""
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1] == name:
            yield child


def _nearest_endpoint(point: TrackPoint, target: datetime, max_gap_s: int):
    if abs((point[0] - target).total_seconds()) <= max_gap_s:
        return point[1], point[2]
    return None


def _interpolate(before: TrackPoint, after: TrackPoint, target: datetime, max_gap_s: int):
    span = (after[0] - before[0]).total_seconds()
    if span > max_gap_s:
        return None
    frac = (target - before[0]).total_seconds() / span if span else 0.0
    lat = before[1] + frac * (after[1] - before[1])
    lon = before[2] + frac * (after[2] - before[2])
    return lat, lon


def _nearest_in_segment(before: TrackPoint, after: TrackPoint, target: datetime, max_gap_s: int):
    nearer = before if (target - before[0]) <= (after[0] - target) else after
    return _nearest_endpoint(nearer, target, max_gap_s)
