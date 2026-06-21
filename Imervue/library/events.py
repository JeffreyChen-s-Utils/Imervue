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
# A burst is a rapid continuous-shooting run: frames within ~2s of each other.
DEFAULT_BURST_GAP_SECONDS = 2.0
DEFAULT_BURST_MIN_SIZE = 3


def group_by_time_gap(
    items: list[tuple[str, datetime]], gap_seconds: float = DEFAULT_GAP_SECONDS,
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
    paths: Iterable[str], gap_seconds: float = DEFAULT_GAP_SECONDS,
) -> list[tuple[str, list[str]]]:
    """Group *paths* into ``(label, paths)`` events by capture date."""
    from Imervue.library.date_import import extract_capture_date
    items = [(p, extract_capture_date(p)) for p in paths]
    dated = [(p, when) for p, when in items if when is not None]
    return [
        (format_event_label(group), [path for path, _when in group])
        for group in group_by_time_gap(dated, gap_seconds)
    ]


def detect_bursts(
    items: list[tuple[str, datetime]],
    gap_seconds: float = DEFAULT_BURST_GAP_SECONDS,
    min_size: int = DEFAULT_BURST_MIN_SIZE,
) -> list[list[tuple[str, datetime]]]:
    """Return runs of >= *min_size* frames each within *gap_seconds* of the next.

    A burst is a rapid continuous-shooting sequence, so singletons and (with the
    default ``min_size``) pairs are not reported — only dense runs survive.
    """
    floor = max(1, int(min_size))
    return [
        group for group in group_by_time_gap(items, gap_seconds)
        if len(group) >= floor
    ]


def build_bursts(
    paths: Iterable[str],
    gap_seconds: float = DEFAULT_BURST_GAP_SECONDS,
    min_size: int = DEFAULT_BURST_MIN_SIZE,
) -> list[list[str]]:
    """Return path-only burst groups (rapid runs) from *paths* by capture time."""
    from Imervue.library.date_import import extract_capture_date
    items = [(p, extract_capture_date(p)) for p in paths]
    dated = [(p, when) for p, when in items if when is not None]
    return [
        [path for path, _when in group]
        for group in detect_bursts(dated, gap_seconds, min_size)
    ]
