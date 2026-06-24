"""Temporal rules gating when a pet ``ScheduledEvent`` may fire.

A scheduled event already fires every ``every_seconds`` (monotonic). A
:class:`ScheduleRule` adds wall-clock gates on top: an allowed hour window and
an allowed-weekday set, so a "time for a break" line can be told to stay quiet
overnight or only nag on workdays. Pure functions — the engine consults
:func:`rule_allows` with the current ``datetime`` before firing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

_MAX_HOUR = 23
_MAX_WEEKDAY = 6


@dataclass
class ScheduleRule:
    """When a scheduled event is allowed to fire (wall-clock gating).

    ``start_hour`` / ``end_hour`` bound the allowed local-time window as
    ``[start_hour, end_hour)`` and apply only when BOTH are set; if
    ``end_hour <= start_hour`` the window wraps past midnight (e.g. 22 → 7 is
    "overnight"). ``weekdays`` restricts firing to those ``Monday=0 … Sunday=6``
    days. Unset fields impose no restriction.
    """

    start_hour: int | None = None
    end_hour: int | None = None
    weekdays: list[int] | None = None

    def is_empty(self) -> bool:
        """True when the rule restricts nothing (no window, no weekday set)."""
        no_window = self.start_hour is None or self.end_hour is None
        return no_window and not self.weekdays


def hour_in_window(hour: int, start: int, end: int) -> bool:
    """True when *hour* is in ``[start, end)``, supporting a midnight wrap."""
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def rule_allows(rule: ScheduleRule | None, when: datetime) -> bool:
    """True when *rule* permits firing at the wall-clock time *when*."""
    if rule is None or rule.is_empty():
        return True
    if rule.weekdays is not None and when.weekday() not in rule.weekdays:
        return False
    if rule.start_hour is not None and rule.end_hour is not None:
        return hour_in_window(when.hour, rule.start_hour, rule.end_hour)
    return True


def _coerce_hour(value: Any) -> int | None:
    try:
        hour = int(value)
    except (TypeError, ValueError):
        return None
    return hour if 0 <= hour <= _MAX_HOUR else None


def _coerce_weekdays(value: Any) -> list[int] | None:
    if not isinstance(value, list):
        return None
    days = sorted({
        int(d) for d in value
        if isinstance(d, (int, float)) and not isinstance(d, bool)
        and 0 <= int(d) <= _MAX_WEEKDAY
    })
    return days or None


def rule_from_dict(value: Any) -> ScheduleRule | None:
    """Parse a rule sub-dict from a ``.petscript.json`` scheduled entry."""
    if not isinstance(value, dict):
        return None
    rule = ScheduleRule(
        start_hour=_coerce_hour(value.get("start_hour")),
        end_hour=_coerce_hour(value.get("end_hour")),
        weekdays=_coerce_weekdays(value.get("weekdays")),
    )
    return None if rule.is_empty() else rule


def rule_to_dict(rule: ScheduleRule | None) -> dict[str, Any] | None:
    """Serialise a rule back to a JSON-friendly dict, or None when empty."""
    if rule is None or rule.is_empty():
        return None
    out: dict[str, Any] = {}
    if rule.start_hour is not None and rule.end_hour is not None:
        out["start_hour"] = rule.start_hour
        out["end_hour"] = rule.end_hour
    if rule.weekdays:
        out["weekdays"] = list(rule.weekdays)
    return out
