"""Qt-free form-data conversion for the pet-script editor.

:func:`script_from_form_data` turns the flat dict the editor dialog
produces into a :class:`PetScript`; the helpers normalise each section
and drop malformed scheduled entries. Testable without Qt.
"""
from __future__ import annotations

from Imervue.desktop_pet.pet_script import (
    TIME_OF_DAY_BANDS,
    PetScript,
    ScheduledEvent,
)
from Imervue.desktop_pet.schedule_rules import ScheduleRule, rule_from_dict


def _coerce_rule(value: object) -> ScheduleRule | None:
    """Normalize a carried schedule rule: keep a ScheduleRule, coerce a dict from
    raw form data, else None. Lets the editor round-trip preserve the wall-clock
    gating instead of silently stripping it."""
    if isinstance(value, ScheduleRule):
        return value
    if isinstance(value, dict):
        return rule_from_dict(value)
    return None


def _parse_scheduled_events(raw: object) -> list[ScheduledEvent]:
    """Build the scheduled-event list from raw form data, skipping bad entries."""
    events: list[ScheduledEvent] = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        try:
            every = float(entry.get("every_seconds", 0))
        except (TypeError, ValueError):
            continue
        messages = entry.get("messages", []) or []
        if every <= 0 or not isinstance(messages, list):
            continue
        events.append(ScheduledEvent(
            every_seconds=every,
            messages=[str(m) for m in messages if isinstance(m, str)],
            rule=_coerce_rule(entry.get("rule")),
        ))
    return events


def script_from_form_data(data: dict) -> PetScript:
    """Convert the dialog's flat form-data dict into a
    :class:`PetScript`. Used by the dialog's OK path; also a clean
    test seam — assertions can compare ``script_from_form_data(...)``
    directly with an expected :class:`PetScript`.

    Form-data keys:

    * ``name`` (str)
    * ``greetings`` (list[str])
    * ``time_of_day_greetings`` (dict[str, list[str]])
    * ``hit_responses`` (dict[str, list[str]])
    * ``motion_lines`` (dict[str, list[str]])
    * ``scheduled`` (list[dict] — each ``{every_seconds, messages}``)
    """
    return PetScript(
        name=str(data.get("name", "")),
        greetings=list(_string_list(data.get("greetings"))),
        time_of_day_greetings={
            band: list(_string_list(
                (data.get("time_of_day_greetings") or {}).get(band, []),
            ))
            for band in TIME_OF_DAY_BANDS
        },
        hit_responses={
            str(k): list(_string_list(v))
            for k, v in (data.get("hit_responses") or {}).items()
            if isinstance(k, str) and k
        },
        motion_lines={
            str(k): list(_string_list(v))
            for k, v in (data.get("motion_lines") or {}).items()
            if isinstance(k, str) and k
        },
        scheduled=_parse_scheduled_events(data.get("scheduled")),
    )


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(v) for v in value if isinstance(v, str))
