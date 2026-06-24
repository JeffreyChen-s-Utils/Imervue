"""Tests for capture-time correction planning."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from Imervue.library.capture_time import (
    EXIF_DATETIME_FORMAT,
    delta_to_match,
    plan_exif_rewrites,
    shift_capture_time,
)


def _items():
    return [
        ("a.jpg", datetime(2024, 1, 1, 12, 0, 0)),
        ("b.jpg", datetime(2024, 1, 1, 12, 30, 0)),
    ]


# ---------------------------------------------------------------------------
# delta_to_match
# ---------------------------------------------------------------------------


def test_delta_to_match_positive():
    actual = datetime(2024, 1, 1, 10, 0, 0)
    correct = datetime(2024, 1, 1, 13, 0, 0)
    assert delta_to_match(actual, correct) == timedelta(hours=3)


def test_delta_to_match_negative():
    actual = datetime(2024, 1, 1, 13, 0, 0)
    correct = datetime(2024, 1, 1, 12, 0, 0)
    assert delta_to_match(actual, correct) == timedelta(hours=-1)


def test_delta_to_match_round_trips_with_shift():
    actual = datetime(2024, 6, 1, 9, 15, 0)
    correct = datetime(2024, 6, 1, 11, 45, 30)
    delta = delta_to_match(actual, correct)
    assert shift_capture_time([("x", actual)], delta)[0][1] == correct


# ---------------------------------------------------------------------------
# shift_capture_time
# ---------------------------------------------------------------------------


def test_shift_adds_delta_to_all():
    out = shift_capture_time(_items(), timedelta(hours=2))
    assert out[0][1] == datetime(2024, 1, 1, 14, 0, 0)
    assert out[1][1] == datetime(2024, 1, 1, 14, 30, 0)


def test_shift_negative_delta():
    out = shift_capture_time(_items(), timedelta(minutes=-90))
    assert out[0][1] == datetime(2024, 1, 1, 10, 30, 0)


def test_shift_zero_delta_is_unchanged():
    items = _items()
    assert shift_capture_time(items, timedelta(0)) == items


def test_shift_preserves_order_and_paths():
    out = shift_capture_time(_items(), timedelta(days=1))
    assert [p for p, _ in out] == ["a.jpg", "b.jpg"]


def test_shift_empty_list():
    assert shift_capture_time([], timedelta(hours=1)) == []


def test_shift_overflow_raises():
    with pytest.raises(OverflowError):
        shift_capture_time([("x", datetime.max)], timedelta(days=1))


# ---------------------------------------------------------------------------
# plan_exif_rewrites
# ---------------------------------------------------------------------------


def test_plan_formats_exif_string():
    out = plan_exif_rewrites(_items(), timedelta(hours=2))
    assert out[0] == ("a.jpg", "2024:01:01 14:00:00")


def test_plan_string_parses_back():
    out = plan_exif_rewrites(_items(), timedelta(hours=2))
    parsed = datetime.strptime(out[1][1], EXIF_DATETIME_FORMAT)
    assert parsed == datetime(2024, 1, 1, 14, 30, 0)


def test_plan_empty_list():
    assert plan_exif_rewrites([], timedelta(hours=1)) == []
