"""Action recorder + replay — the data layer behind macro-style automation.

A simple producer / consumer pair the dispatcher and menu / dialog
layer can call into:

* :class:`Action` — frozen ``(kind, params, timestamp)`` triple.
* :class:`ActionRecording` — named ordered list of Actions.
* :class:`ActionRecorder` — flip-on / flip-off recorder. The
  workspace dispatcher calls ``record(kind, params)`` for every
  operation it routes; if the recorder is "armed" the action lands
  in the active recording, otherwise it's silently dropped.
* :func:`replay` — walk a recording and call a callable target with
  each action's ``(kind, params)``. Replay is dumb on purpose — the
  caller wires it up to the same dispatcher entry points the
  recorder hooked into, so the macro semantics are "do exactly what
  the user did originally".

Persistence: a list of recordings round-trips through
``user_setting_dict["paint_action_recordings"]`` so a long-lived
macro library survives restart. Corrupt entries silently drop on
load.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_action_recordings"
MAX_RECORDINGS = 256
MAX_ACTIONS_PER_RECORDING = 100_000


@dataclass(frozen=True)
class Action:
    """One recorded action."""

    kind: str
    params: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not str(self.kind).strip():
            raise ValueError("action kind must be non-empty")
        if not isinstance(self.params, dict):
            raise ValueError(
                f"params must be a dict, got {type(self.params).__name__}",
            )

    def to_dict(self) -> dict:
        return {
            "kind": str(self.kind),
            "params": dict(self.params),
            "timestamp": float(self.timestamp),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Action:
        if not isinstance(raw, dict):
            raise ValueError(
                f"action payload must be a dict, got {type(raw).__name__}",
            )
        kind = str(raw.get("kind", "")).strip()
        if not kind:
            raise ValueError("action kind must be non-empty")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            params = {}
        return cls(
            kind=kind,
            params=params,
            timestamp=float(raw.get("timestamp", 0.0)),
        )


@dataclass
class ActionRecording:
    """Named ordered list of Actions."""

    name: str
    actions: list[Action] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("recording name must be non-empty")
        if len(self.actions) > MAX_ACTIONS_PER_RECORDING:
            raise ValueError(
                f"recording {self.name!r} has {len(self.actions)} actions; "
                f"max is {MAX_ACTIONS_PER_RECORDING}",
            )

    def append(self, action: Action) -> bool:
        """Append ``action`` if the cap hasn't been reached."""
        if len(self.actions) >= MAX_ACTIONS_PER_RECORDING:
            return False
        self.actions.append(action)
        return True

    def to_dict(self) -> dict:
        return {
            "name": str(self.name),
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> ActionRecording:
        if not isinstance(raw, dict):
            raise ValueError(
                f"recording payload must be a dict, got {type(raw).__name__}",
            )
        name = str(raw.get("name", "")).strip() or "recording"
        actions_raw = raw.get("actions") or []
        if not isinstance(actions_raw, list):
            actions_raw = []
        actions: list[Action] = []
        for entry in actions_raw[:MAX_ACTIONS_PER_RECORDING]:
            try:
                actions.append(Action.from_dict(entry))
            except (ValueError, TypeError):
                continue
        return cls(name=name, actions=actions)


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


class ActionRecorder:
    """Flip-on / flip-off recorder.

    Workflow::

        recorder = ActionRecorder()
        recorder.start("Frame intro")
        # … workspace dispatches actions, each calling recorder.record …
        recording = recorder.stop()  # returns the captured ActionRecording

    Calls to :meth:`record` while not recording are silently dropped so
    the dispatcher can wire it in unconditionally.
    """

    def __init__(self) -> None:
        self._active: ActionRecording | None = None
        self._start_time: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._active is not None

    def start(self, name: str) -> None:
        """Begin a fresh recording with the supplied name."""
        if self._active is not None:
            raise RuntimeError(
                f"recorder is already recording {self._active.name!r}",
            )
        self._active = ActionRecording(name=name)
        self._start_time = time.monotonic()

    def stop(self) -> ActionRecording | None:
        """Stop recording and return the captured recording. Returns
        ``None`` when the recorder wasn't active."""
        recording = self._active
        self._active = None
        return recording

    def record(self, kind: str, params: dict | None = None) -> bool:
        """Capture one action. Returns ``True`` if it landed in the
        active recording, ``False`` otherwise."""
        if self._active is None:
            return False
        timestamp = time.monotonic() - self._start_time
        action = Action(
            kind=kind, params=dict(params or {}), timestamp=timestamp,
        )
        return self._active.append(action)


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def replay(
    recording: ActionRecording,
    target: Callable[[str, dict], None],
    *,
    kinds_filter: tuple[str, ...] | None = None,
) -> int:
    """Walk ``recording`` and call ``target(kind, params)`` for each action.

    Returns the count of actions actually replayed (i.e. that passed
    the optional ``kinds_filter``). The target may raise — replay
    propagates the first exception so the caller knows which action
    failed and can resume from there.
    """
    count = 0
    for action in recording.actions:
        if kinds_filter is not None and action.kind not in kinds_filter:
            continue
        target(action.kind, dict(action.params))
        count += 1
    return count


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_recordings(recordings: list[ActionRecording]) -> None:
    """Persist a list of recordings (whole-list replace)."""
    if len(recordings) > MAX_RECORDINGS:
        raise ValueError(
            f"refusing to save {len(recordings)} recordings; "
            f"max is {MAX_RECORDINGS}",
        )
    user_setting_dict[_USER_SETTING_KEY] = [
        rec.to_dict() for rec in recordings
    ]
    schedule_save()


def load_recordings() -> list[ActionRecording]:
    """Return persisted recordings; corrupt entries silently dropped."""
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[ActionRecording] = []
    for entry in raw:
        try:
            out.append(ActionRecording.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return out
