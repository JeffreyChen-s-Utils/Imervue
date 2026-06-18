"""Group photos into "events" by the time gaps between captures.

A burst of photos shot within a few hours is one event; a gap larger than the
threshold starts a new one. The grouping and labelling are pure and unit-tested;
:func:`build_events` reads capture dates (reusing date_import) and labels each
group by its date span.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

_SECONDS_PER_HOUR = 3600
DEFAULT_GAP_HOURS = 4
DEFAULT_GAP_SECONDS = DEFAULT_GAP_HOURS * _SECONDS_PER_HOUR


def group_by_time_gap(
    items: list[tuple[str, datetime]], gap_seconds: int = DEFAULT_GAP_SECONDS,
) -> list[list[tuple[str, datetime]]]:
    """Split ``(path, when)`` items into runs separated by gaps > *gap_seconds*."""
    groups: list[list[tuple[str, datetime]]] = []
    current: list[tuple[str, datetime]] = []
    previous: datetime | None = None
    for path, when in sorted(items, key=lambda item: item[1]):
        if previous is not None and (when - previous).total_seconds() > gap_seconds:
            groups.append(current)
            current = []
        current.append((path, when))
        previous = when
    if current:
        groups.append(current)
    return groups


def format_event_label(group: list[tuple[str, datetime]]) -> str:
    """Label a group by its date span (single day, or ``start – end``)."""
    start, end = group[0][1], group[-1][1]
    if start.date() == end.date():
        return start.strftime("%Y-%m-%d")
    return f"{start.strftime('%Y-%m-%d')} – {end.strftime('%Y-%m-%d')}"


def build_events(
    paths: Iterable[str], gap_seconds: int = DEFAULT_GAP_SECONDS,
) -> list[tuple[str, list[str]]]:
    """Group *paths* into ``(label, paths)`` events by capture date."""
    from Imervue.library.date_import import extract_capture_date
    items = [(p, extract_capture_date(p)) for p in paths]
    dated = [(p, when) for p, when in items if when is not None]
    return [
        (format_event_label(group), [path for path, _when in group])
        for group in group_by_time_gap(dated, gap_seconds)
    ]
