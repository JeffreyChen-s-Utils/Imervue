"""Tests for time-gap event grouping."""
from __future__ import annotations

from datetime import datetime

from Imervue.library.events import (
    build_events,
    format_event_label,
    group_by_time_gap,
)


def _items():
    return [
        ("a.jpg", datetime(2024, 7, 1, 10, 0, 0)),
        ("b.jpg", datetime(2024, 7, 1, 10, 30, 0)),   # same burst
        ("c.jpg", datetime(2024, 7, 5, 9, 0, 0)),      # days later → new event
    ]


def test_group_splits_on_large_gap():
    groups = group_by_time_gap(_items(), gap_seconds=3600)
    assert [len(g) for g in groups] == [2, 1]


def test_group_orders_unsorted_input():
    shuffled = list(reversed(_items()))
    groups = group_by_time_gap(shuffled, gap_seconds=3600)
    assert groups[0][0][0] == "a.jpg"  # earliest first


def test_group_single_event_when_within_gap():
    groups = group_by_time_gap(_items()[:2], gap_seconds=3600)
    assert len(groups) == 1


def test_group_empty():
    assert group_by_time_gap([]) == []


def test_format_event_label_same_day():
    group = [("a", datetime(2024, 7, 1, 9)), ("b", datetime(2024, 7, 1, 18))]
    assert format_event_label(group) == "2024-07-01"


def test_format_event_label_span():
    group = [("a", datetime(2024, 7, 1)), ("b", datetime(2024, 7, 3))]
    assert format_event_label(group) == "2024-07-01 – 2024-07-03"


def test_build_events_uses_capture_dates(monkeypatch):
    dates = {
        "x.jpg": datetime(2024, 1, 1, 8, 0, 0),
        "y.jpg": datetime(2024, 1, 1, 8, 20, 0),
        "z.jpg": datetime(2024, 3, 1, 8, 0, 0),
    }
    from Imervue.library import date_import
    monkeypatch.setattr(date_import, "extract_capture_date", lambda p: dates.get(p))
    result = build_events(["x.jpg", "y.jpg", "z.jpg"], gap_seconds=3600)
    assert [label for label, _ in result] == ["2024-01-01", "2024-03-01"]
    assert result[0][1] == ["x.jpg", "y.jpg"]
