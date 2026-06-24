"""Tests for time-gap event grouping."""
from __future__ import annotations

from datetime import datetime, timedelta

from Imervue.library.events import (
    build_bursts,
    build_events,
    detect_bursts,
    format_event_label,
    group_by_time_gap,
)

_BURST_BASE = datetime(2024, 1, 1, 12, 0, 0)


def _burst_items(offsets):
    """``(path, when)`` items at the given second offsets from a fixed base."""
    return [
        (f"p{i}", _BURST_BASE + timedelta(seconds=off))
        for i, off in enumerate(offsets)
    ]


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


# ---------------------------------------------------------------------------
# Burst detection
# ---------------------------------------------------------------------------


def test_detect_bursts_finds_dense_run():
    items = _burst_items([0, 0.5, 1.0, 100])  # three rapid, then a far one
    bursts = detect_bursts(items, gap_seconds=2.0, min_size=3)
    assert len(bursts) == 1
    assert [path for path, _ in bursts[0]] == ["p0", "p1", "p2"]


def test_detect_bursts_ignores_runs_below_min_size():
    items = _burst_items([0, 0.5, 100, 100.5])  # two pairs, neither a burst
    assert detect_bursts(items, gap_seconds=2.0, min_size=3) == []


def test_detect_bursts_min_size_two_keeps_pairs():
    items = _burst_items([0, 0.5, 100])
    bursts = detect_bursts(items, gap_seconds=2.0, min_size=2)
    assert len(bursts) == 1 and len(bursts[0]) == 2


def test_detect_bursts_separates_two_bursts():
    items = _burst_items([0, 0.3, 0.6, 100, 100.3, 100.6])
    bursts = detect_bursts(items, gap_seconds=2.0, min_size=3)
    assert [len(g) for g in bursts] == [3, 3]


def test_detect_bursts_empty():
    assert detect_bursts([], min_size=3) == []


def test_build_bursts_uses_capture_dates(monkeypatch):
    dates = {
        "a.jpg": _BURST_BASE,
        "b.jpg": _BURST_BASE + timedelta(seconds=0.4),
        "c.jpg": _BURST_BASE + timedelta(seconds=0.8),
        "d.jpg": _BURST_BASE + timedelta(seconds=600),  # lone shot
    }
    from Imervue.library import date_import
    monkeypatch.setattr(date_import, "extract_capture_date", lambda p: dates.get(p))
    bursts = build_bursts(["a.jpg", "b.jpg", "c.jpg", "d.jpg"], min_size=3)
    assert bursts == [["a.jpg", "b.jpg", "c.jpg"]]
