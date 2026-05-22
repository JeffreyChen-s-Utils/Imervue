"""Pet-script engine — user-customisable messages + scheduled events.

The Desktop Pet's speech bubble used to draw from a hard-coded
``DEFAULT_GREETINGS`` tuple. That made it impossible to give the
pet a personality without editing source. This module replaces the
tuple with a small JSON-backed engine the user can author and load
from the workspace tab.

JSON schema (versioned so we can grow without breaking older files):

.. code-block:: json

    {
        "version": 1,
        "name": "March 7th",
        "greetings": ["Hello!", "Hi there!"],
        "time_of_day_greetings": {
            "morning": ["Good morning!"],
            "afternoon": ["Afternoon!"],
            "evening": ["Good evening!"],
            "night": ["Still up?"]
        },
        "hit_responses": {
            "head": ["Don't poke me!", "Hey!"],
            "body": ["Ticklish!"]
        },
        "motion_lines": {
            "wave": ["Hi!", "Hello!"]
        },
        "scheduled": [
            {"every_seconds": 600, "messages": ["Time for a break?"]}
        ]
    }

* ``greetings`` — used when the user clicks the pet and no hit
  area matches.
* ``time_of_day_greetings`` — same trigger as ``greetings``, but
  takes priority and picks based on local clock band
  (``morning`` 05–11, ``afternoon`` 12–17, ``evening`` 18–21,
  ``night`` 22–04). Missing bands fall back to ``greetings``.
* ``hit_responses`` — keyed by ``HitArea.id``; one of the lines
  pops when that area is clicked. Overrides the default greeting.
* ``motion_lines`` — keyed by ``Motion.name``; one of the lines
  pops when that motion starts (either from a hit area or from
  the context menu).
* ``scheduled`` — list of timer-driven entries. Each fires after
  ``every_seconds`` of clock time, picking randomly from
  ``messages``.

Every list is sampled round-robin so consecutive triggers don't
repeat the same line — same UX the hard-coded greetings already
gave.

The loader is forward-compat: unknown top-level keys are ignored
(so a future v2 file still parses on an older runtime), and any
malformed entry inside a list is skipped rather than failing the
whole load.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("Imervue.desktop_pet.pet_script")

CURRENT_SCHEMA_VERSION: int = 1
"""Bumps on schema-breaking changes. Older files keep working
because the loader merges defaults; newer files load on older
runtimes by ignoring unknown fields."""

DEFAULT_GREETINGS: tuple[str, ...] = (
    "Hello!",
    "Hi there!",
    "What's up?",
    "Hey!",
    "Need anything?",
)
"""Used as the fallback line set when no script is loaded — same
five lines the desktop pet shipped with before scripting. Kept here
(rather than in ``pet_window``) so callers can construct an empty
script that still surfaces the default voice."""

TIME_OF_DAY_BANDS: tuple[str, ...] = ("morning", "afternoon", "evening", "night")
"""Canonical ordering of the four bands. Anything outside this set
in a loaded script is dropped during coercion so the engine never
has to defend against typo'd band keys at sample time."""


def time_of_day_band(hour: int) -> str:
    """Map a 24-hour clock value to its band name.

    Bands match common-sense thresholds:

    * ``morning``   — 05 ≤ h < 12
    * ``afternoon`` — 12 ≤ h < 18
    * ``evening``   — 18 ≤ h < 22
    * ``night``     — 22 ≤ h < 24  *or*  0 ≤ h < 5

    Pure helper so tests inject any hour without monkey-patching the
    clock. ``hour`` is wrapped to ``[0, 24)`` so timezone-offset
    arithmetic that produces 25 or -3 still lands somewhere sane.
    """
    h = int(hour) % 24
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 18:
        return "afternoon"
    if 18 <= h < 22:
        return "evening"
    return "night"


@dataclass
class ScheduledEvent:
    """One timer-driven line set. The engine fires it whenever
    ``every_seconds`` of wall-clock time has passed since the last
    fire — using ``time.monotonic`` so suspending the laptop or
    changing the system clock doesn't make the pet binge-fire all
    its queued lines at once.
    """

    every_seconds: float
    messages: list[str] = field(default_factory=list)


@dataclass
class PetScript:
    """In-memory representation of one ``.petscript.json`` file."""

    version: int = CURRENT_SCHEMA_VERSION
    name: str = ""
    greetings: list[str] = field(default_factory=list)
    time_of_day_greetings: dict[str, list[str]] = field(default_factory=dict)
    hit_responses: dict[str, list[str]] = field(default_factory=dict)
    motion_lines: dict[str, list[str]] = field(default_factory=dict)
    scheduled: list[ScheduledEvent] = field(default_factory=list)

    @classmethod
    def default(cls) -> PetScript:
        """Build the baseline script the engine falls back to when
        no file is loaded. The greetings carry the same five
        lines the pet shipped with so the UX is unchanged when no
        custom script is in play."""
        return cls(
            version=CURRENT_SCHEMA_VERSION,
            name="default",
            greetings=list(DEFAULT_GREETINGS),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "greetings": list(self.greetings),
            "time_of_day_greetings": {
                k: list(v) for k, v in self.time_of_day_greetings.items()
            },
            "hit_responses": {k: list(v) for k, v in self.hit_responses.items()},
            "motion_lines": {k: list(v) for k, v in self.motion_lines.items()},
            "scheduled": [
                {
                    "every_seconds": ev.every_seconds,
                    "messages": list(ev.messages),
                }
                for ev in self.scheduled
            ],
        }


# ---------------------------------------------------------------
# Loading
# ---------------------------------------------------------------


class PetScriptError(ValueError):
    """Raised when a script file can't be parsed at all (bad JSON,
    not a dict at top level). Field-level garbage is silently
    coerced to defaults so a typo in one entry doesn't lose the
    whole file."""


def load_script(path: str | Path) -> PetScript:
    """Read ``path`` and return a :class:`PetScript`. Raises
    :class:`PetScriptError` when the file is missing or not parseable
    JSON; everything else (typos, unknown keys, garbage values)
    coerces to defaults so the pet keeps working with a partial
    script."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise PetScriptError(f"can't read {p}: {exc}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PetScriptError(f"{p}: invalid JSON ({exc})") from exc
    if not isinstance(raw, dict):
        raise PetScriptError(f"{p}: top-level must be a JSON object")
    return _coerce_script(raw)


def save_script(script: PetScript, path: str | Path) -> None:
    """Write ``script`` to ``path`` as pretty-printed JSON. Used
    by the workspace's "save current script" button so the user
    can hand-edit the result."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(script.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _coerce_script(raw: dict[str, Any]) -> PetScript:
    """Convert a raw dict to a :class:`PetScript`, defaulting any
    missing / wrong-typed fields. Quiet about errors — a noisy
    loader would bury the user's typos in stderr noise instead of
    just falling back."""
    return PetScript(
        version=_coerce_int(raw.get("version"), CURRENT_SCHEMA_VERSION),
        name=str(raw.get("name", "")),
        greetings=_coerce_str_list(raw.get("greetings")),
        time_of_day_greetings=_coerce_time_of_day(raw.get("time_of_day_greetings")),
        hit_responses=_coerce_str_list_dict(raw.get("hit_responses")),
        motion_lines=_coerce_str_list_dict(raw.get("motion_lines")),
        scheduled=_coerce_scheduled(raw.get("scheduled")),
    )


def _coerce_time_of_day(value: Any) -> dict[str, list[str]]:
    """Same shape as :func:`_coerce_str_list_dict` but drops any key
    that isn't in :data:`TIME_OF_DAY_BANDS`. Typo'd bands (``"mornig"``)
    silently disappear instead of becoming a never-firing bucket."""
    if not isinstance(value, dict):
        return {}
    return {
        str(key): _coerce_str_list(val)
        for key, val in value.items()
        if isinstance(val, list) and str(key) in TIME_OF_DAY_BANDS
    }


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _coerce_str_list_dict(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): _coerce_str_list(val)
        for key, val in value.items()
        if isinstance(val, list)
    }


def _coerce_scheduled(value: Any) -> list[ScheduledEvent]:
    if not isinstance(value, list):
        return []
    out: list[ScheduledEvent] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        try:
            every = float(entry.get("every_seconds", 0))
        except (TypeError, ValueError):
            continue
        if every <= 0:
            continue
        out.append(ScheduledEvent(
            every_seconds=every,
            messages=_coerce_str_list(entry.get("messages")),
        ))
    return out


# ---------------------------------------------------------------
# Runtime engine
# ---------------------------------------------------------------


class PetScriptEngine:
    """Runtime that picks lines from a :class:`PetScript`.

    Owned by the pet window; consulted on click + on a periodic
    tick (matches the speech-bubble cadence). Sampling is
    round-robin per list so the user doesn't see the same line
    twice in a row even on small line sets — the same UX policy
    the hard-coded greetings used before scripting existed.
    """

    def __init__(self, script: PetScript | None = None) -> None:
        self._script: PetScript = script or PetScript.default()
        # Per-list cursors. Keyed by an opaque list-identity tag
        # so each named line bucket cycles independently — clicking
        # the head then the body shouldn't fast-forward the body's
        # rotation.
        self._cursors: dict[str, int] = {}
        # Wall-clock anchors for each ``ScheduledEvent``. Started
        # at engine init so the first fire lands ``every_seconds``
        # after the pet appears, not immediately.
        self._sched_anchors: list[float] = [
            time.monotonic() for _ in self._script.scheduled
        ]

    # ---- public API --------------------------------------------

    def set_script(self, script: PetScript) -> None:
        """Swap in a new script. Cursors reset so the user sees
        the new content from the start of every list."""
        self._script = script
        self._cursors.clear()
        self._sched_anchors = [time.monotonic() for _ in script.scheduled]

    def script(self) -> PetScript:
        return self._script

    def pick_for_hit_area(self, area_id: str | None) -> str | None:
        """Click on a hit area → its line bucket. Returns ``None``
        when the bucket is empty so the caller can fall through to
        the generic greeting set."""
        if not area_id:
            return None
        lines = self._script.hit_responses.get(area_id)
        if not lines:
            return None
        return self._next_line(f"hit:{area_id}", lines)

    def pick_for_motion(self, motion_name: str | None) -> str | None:
        """Motion started → matching line. ``None`` means "no
        message configured for this motion" — caller may want to
        stay silent rather than fall back to a greeting."""
        if not motion_name:
            return None
        lines = self._script.motion_lines.get(motion_name)
        if not lines:
            return None
        return self._next_line(f"motion:{motion_name}", lines)

    def pick_time_of_day_greeting(self, *, hour: int | None = None) -> str | None:
        """Pick a greeting for the current local-clock band, or
        ``None`` when the band has no lines authored.

        ``hour`` lets tests inject a deterministic clock; production
        callers pass nothing and we read ``datetime.now().hour``.
        Returning ``None`` (not falling back to the plain greetings)
        is deliberate — the pet window chains this in front of
        :meth:`pick_greeting` so the caller controls the fallback.
        """
        if hour is None:
            hour = datetime.now().hour
        band = time_of_day_band(hour)
        lines = self._script.time_of_day_greetings.get(band)
        if not lines:
            return None
        return self._next_line(f"tod:{band}", lines)

    def pick_greeting(self) -> str | None:
        """Default click line. Falls back through three layers so
        a partial script still produces something:

        1. The script's own ``greetings`` list, if non-empty.
        2. :data:`DEFAULT_GREETINGS`, the shipped fallback.
        3. ``None`` if even that's somehow empty (defensive).
        """
        if self._script.greetings:
            return self._next_line("greetings", self._script.greetings)
        if DEFAULT_GREETINGS:
            return self._next_line("default_greetings", list(DEFAULT_GREETINGS))
        return None

    def due_scheduled_message(self) -> str | None:
        """Called from the pet window's tick. Returns one message
        string if any ``ScheduledEvent`` is overdue, or ``None``.
        On fire, the entry's anchor resets so the next fire is
        ``every_seconds`` away from now (drift-free relative to
        the moment we fired — not relative to the original
        anchor)."""
        now = time.monotonic()
        for index, event in enumerate(self._script.scheduled):
            anchor = self._sched_anchors[index]
            if now - anchor < event.every_seconds:
                continue
            self._sched_anchors[index] = now
            if not event.messages:
                continue
            return self._next_line(f"sched:{index}", event.messages)
        return None

    # ---- internals ---------------------------------------------

    def _next_line(self, bucket_key: str, lines: list[str]) -> str | None:
        """Round-robin pick. The cursor is stored per bucket so
        an empty bucket (after editing) gracefully starts the next
        non-empty bucket from index 0."""
        if not lines:
            return None
        cursor = self._cursors.get(bucket_key, 0) % len(lines)
        line = lines[cursor]
        self._cursors[bucket_key] = (cursor + 1) % len(lines)
        return line
