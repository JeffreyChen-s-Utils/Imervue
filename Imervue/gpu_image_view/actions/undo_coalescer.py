"""Coalesce rapid develop edits into single undo steps.

A slider drag emits one edit per frame, so a two-second drag becomes dozens of
undo steps to click back through. ``recipe_commands`` deliberately does not
merge consecutive commands; this provides the pure grouping logic a caller can
apply before pushing edits onto the undo stack. It works on a neutral
:class:`EditEvent` stream (field / old / new / time) so it needs no Qt — the
undo layer maps its commands to and from these events. Pure list work.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

DEFAULT_WINDOW_SECONDS = 0.5


@dataclass(frozen=True)
class EditEvent:
    """One field edit: the field name, its old/new values and a timestamp."""

    field: str
    old: Any
    new: Any
    time: float


def coalesce_edits(
    events: Sequence[EditEvent], *, window: float = DEFAULT_WINDOW_SECONDS,
) -> list[EditEvent]:
    """Merge runs of same-field edits no more than *window* seconds apart.

    A run collapses to one event keeping the first ``old`` and last ``new`` (and
    the first timestamp). A different field, or a gap longer than *window*,
    starts a new run. Input order is preserved; inputs are not mutated.
    """
    out: list[EditEvent] = []
    for event in events:
        if out and _extends_run(out[-1], event, window):
            previous = out[-1]
            out[-1] = EditEvent(previous.field, previous.old, event.new, previous.time)
        else:
            out.append(event)
    return out


def _extends_run(previous: EditEvent, event: EditEvent, window: float) -> bool:
    return event.field == previous.field and 0.0 <= event.time - previous.time <= window


def drop_noop_edits(events: Sequence[EditEvent]) -> list[EditEvent]:
    """Drop edits whose final value equals its original (e.g. dragged and back)."""
    return [event for event in events if event.old != event.new]


def compress_history(
    events: Sequence[EditEvent], *, window: float = DEFAULT_WINDOW_SECONDS,
) -> list[EditEvent]:
    """Coalesce same-field runs, then drop the resulting no-op edits."""
    return drop_noop_edits(coalesce_edits(events, window=window))
