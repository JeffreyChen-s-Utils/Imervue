"""Editing a pet script must not strip a scheduled event's wall-clock rule.

The visual editor only edits interval + messages, but it must carry each entry's
ScheduleRule through unchanged -- dropping it turned a time-gated reminder (e.g.
weekday 9-17) into one that fires 24/7. These cover the pure carry/parse path and
run on CI (no Qt widget constructed).
"""
from __future__ import annotations

from Imervue.desktop_pet.pet_script_editor import _coerce_rule, _parse_scheduled_events
from Imervue.desktop_pet.schedule_rules import ScheduleRule, rule_from_dict

_RULE_DICT = {"start_hour": 9, "end_hour": 17, "weekdays": [0, 1, 2, 3, 4]}


def test_coerce_rule_keeps_a_schedule_rule():
    rule = rule_from_dict(_RULE_DICT)
    assert isinstance(rule, ScheduleRule)
    assert _coerce_rule(rule) is rule


def test_coerce_rule_from_a_dict():
    coerced = _coerce_rule(_RULE_DICT)
    assert isinstance(coerced, ScheduleRule)
    assert coerced == rule_from_dict(_RULE_DICT)


def test_coerce_rule_none_and_junk_become_none():
    assert _coerce_rule(None) is None
    assert _coerce_rule("nope") is None


def test_parse_scheduled_events_preserves_the_rule():
    rule = rule_from_dict(_RULE_DICT)
    parsed = _parse_scheduled_events([
        {"every_seconds": 600.0, "messages": ["hi"], "rule": rule},
    ])
    assert len(parsed) == 1
    assert parsed[0].rule is rule          # carried through, not stripped to None


def test_parse_scheduled_events_without_rule_is_none():
    parsed = _parse_scheduled_events([
        {"every_seconds": 600.0, "messages": ["hi"]},
    ])
    assert parsed[0].rule is None
