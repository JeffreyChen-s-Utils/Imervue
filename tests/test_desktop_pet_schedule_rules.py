"""Tests for the pet scheduled-event wall-clock rules."""
from __future__ import annotations

from datetime import datetime

import pytest

from Imervue.desktop_pet.schedule_rules import (
    ScheduleRule,
    hour_in_window,
    rule_allows,
    rule_from_dict,
    rule_to_dict,
)

# 2024-01-01 is a Monday (weekday 0); 2024-01-06 is a Saturday (weekday 5).
_MON_10 = datetime(2024, 1, 1, 10, 0)
_MON_3 = datetime(2024, 1, 1, 3, 0)
_SAT_10 = datetime(2024, 1, 6, 10, 0)


# ---------------------------------------------------------------------------
# hour_in_window
# ---------------------------------------------------------------------------


def test_hour_in_window_normal_range():
    assert hour_in_window(10, 9, 17)
    assert not hour_in_window(17, 9, 17)  # end is exclusive
    assert not hour_in_window(8, 9, 17)


def test_hour_in_window_wraps_past_midnight():
    # 22:00 → 07:00 overnight window.
    assert hour_in_window(23, 22, 7)
    assert hour_in_window(3, 22, 7)
    assert not hour_in_window(12, 22, 7)


def test_hour_in_window_degenerate_allows_all():
    assert hour_in_window(5, 8, 8)


# ---------------------------------------------------------------------------
# rule_allows
# ---------------------------------------------------------------------------


def test_none_or_empty_rule_always_allows():
    assert rule_allows(None, _MON_10)
    assert rule_allows(ScheduleRule(), _MON_10)


def test_hour_window_gate():
    rule = ScheduleRule(start_hour=9, end_hour=17)
    assert rule_allows(rule, _MON_10)
    assert not rule_allows(rule, _MON_3)


def test_overnight_window_gate():
    rule = ScheduleRule(start_hour=22, end_hour=7)
    assert rule_allows(rule, _MON_3)        # 03:00 is inside overnight
    assert not rule_allows(rule, _MON_10)   # 10:00 is not


def test_weekday_gate():
    weekdays = ScheduleRule(weekdays=[0, 1, 2, 3, 4])  # Mon-Fri
    assert rule_allows(weekdays, _MON_10)
    assert not rule_allows(weekdays, _SAT_10)


def test_window_and_weekday_combined():
    rule = ScheduleRule(start_hour=9, end_hour=17, weekdays=[0, 1, 2, 3, 4])
    assert rule_allows(rule, _MON_10)
    assert not rule_allows(rule, _SAT_10)   # right hour, wrong day
    assert not rule_allows(rule, _MON_3)    # right day, wrong hour


def test_single_hour_endpoint_is_not_a_window():
    # Only start_hour set -> no window restriction applies.
    assert rule_allows(ScheduleRule(start_hour=9), _MON_3)


# ---------------------------------------------------------------------------
# is_empty + round-trip
# ---------------------------------------------------------------------------


def test_is_empty():
    assert ScheduleRule().is_empty()
    assert ScheduleRule(start_hour=9).is_empty()   # needs both bounds
    assert not ScheduleRule(start_hour=9, end_hour=17).is_empty()
    assert not ScheduleRule(weekdays=[0]).is_empty()


def test_round_trip_through_dict():
    rule = ScheduleRule(start_hour=22, end_hour=7, weekdays=[0, 1, 2, 3, 4])
    data = rule_to_dict(rule)
    assert data == {"start_hour": 22, "end_hour": 7, "weekdays": [0, 1, 2, 3, 4]}
    restored = rule_from_dict(data)
    assert restored == rule


def test_to_dict_none_for_empty():
    assert rule_to_dict(None) is None
    assert rule_to_dict(ScheduleRule()) is None


def test_from_dict_rejects_garbage():
    assert rule_from_dict("nope") is None
    assert rule_from_dict({}) is None
    assert rule_from_dict({"start_hour": 99, "end_hour": 7}) is None  # bad hour


@pytest.mark.parametrize("days,expected", [
    ([0, 6, 3], [0, 3, 6]),       # sorted + de-duped
    ([0, 0, 1], [0, 1]),
    ([7, -1, "x"], None),         # all out of range / wrong type
    ([True, False], None),        # bools are not weekdays
])
def test_weekday_coercion(days, expected):
    rule = rule_from_dict({"weekdays": days})
    assert (rule.weekdays if rule else None) == expected
