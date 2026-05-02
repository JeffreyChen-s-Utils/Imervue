"""Tablet button → action mapping data model.

Wacom / XP-Pen / Huion tablets typically expose a handful of
hardware buttons (eraser end of the stylus, two side buttons, ring
buttons on the tablet body). This module ships the data layer that
binds each one to a workspace action — the dispatcher / settings
panel reads from here to translate hardware events into the right
:class:`ActionRecorder`-friendly callable.

A binding describes: which button (a stable integer ID), what
action it triggers (a kind name like ``"undo"`` / ``"set_tool"`` /
``"toggle_panel"``), and any kind-specific parameters.

Profiles bundle a complete set of bindings under a name so a user
with multiple tablets / setups can switch the whole map in one
click. Persistence rounds through ``user_setting_dict``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_tablet_profiles"
MAX_PROFILES = 32
MAX_BINDINGS_PER_PROFILE = 64


@dataclass(frozen=True)
class TabletBinding:
    """One button → action binding."""

    button_id: int
    action_kind: str
    params: dict = field(default_factory=dict)
    label: str = ""

    def __post_init__(self) -> None:
        if int(self.button_id) < 0:
            raise ValueError(
                f"button_id must be >= 0, got {self.button_id!r}",
            )
        if not str(self.action_kind).strip():
            raise ValueError("action_kind must be non-empty")
        if not isinstance(self.params, dict):
            raise ValueError(
                f"params must be a dict, got {type(self.params).__name__}",
            )

    def to_dict(self) -> dict:
        return {
            "button_id": int(self.button_id),
            "action_kind": str(self.action_kind),
            "params": dict(self.params),
            "label": str(self.label),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> TabletBinding:
        if not isinstance(raw, dict):
            raise ValueError(
                f"binding payload must be a dict, got {type(raw).__name__}",
            )
        # Don't clamp — let __post_init__ reject negatives so the
        # surrounding TabletProfile.from_dict drops the corrupt entry
        # rather than silently rewriting it to button 0.
        try:
            button_id = int(raw.get("button_id", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("button_id must be an integer") from exc
        action_kind = str(raw.get("action_kind", "")).strip()
        if not action_kind:
            raise ValueError("action_kind must be non-empty")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            params = {}
        label = str(raw.get("label", ""))
        return cls(
            button_id=button_id,
            action_kind=action_kind,
            params=params,
            label=label,
        )


@dataclass
class TabletProfile:
    """Named collection of TabletBindings."""

    name: str
    bindings: list[TabletBinding] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("profile name must be non-empty")
        if len(self.bindings) > MAX_BINDINGS_PER_PROFILE:
            raise ValueError(
                f"profile {self.name!r} has {len(self.bindings)} bindings, "
                f"max is {MAX_BINDINGS_PER_PROFILE}",
            )

    def find(self, button_id: int) -> TabletBinding | None:
        for binding in self.bindings:
            if binding.button_id == button_id:
                return binding
        return None

    def set_binding(self, binding: TabletBinding) -> bool:
        """Replace any existing binding for the same button_id, or
        append a new one. Returns ``True`` if anything changed."""
        for i, existing in enumerate(self.bindings):
            if existing.button_id == binding.button_id:
                if existing == binding:
                    return False
                self.bindings[i] = binding
                return True
        if len(self.bindings) >= MAX_BINDINGS_PER_PROFILE:
            raise ValueError(
                f"profile {self.name!r} already has "
                f"{MAX_BINDINGS_PER_PROFILE} bindings",
            )
        self.bindings.append(binding)
        return True

    def remove(self, button_id: int) -> bool:
        for i, binding in enumerate(self.bindings):
            if binding.button_id == button_id:
                del self.bindings[i]
                return True
        return False

    def to_dict(self) -> dict:
        return {
            "name": str(self.name),
            "bindings": [b.to_dict() for b in self.bindings],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> TabletProfile:
        if not isinstance(raw, dict):
            raise ValueError(
                f"profile payload must be a dict, got {type(raw).__name__}",
            )
        name = str(raw.get("name", "")).strip() or "profile"
        raw_bindings = raw.get("bindings") or []
        if not isinstance(raw_bindings, list):
            raw_bindings = []
        bindings: list[TabletBinding] = []
        for entry in raw_bindings[:MAX_BINDINGS_PER_PROFILE]:
            try:
                bindings.append(TabletBinding.from_dict(entry))
            except (ValueError, TypeError):
                continue
        return cls(name=name, bindings=bindings)


# ---------------------------------------------------------------------------
# Built-in starter profiles
# ---------------------------------------------------------------------------


BUILT_IN_PROFILES: tuple[TabletProfile, ...] = (
    TabletProfile(
        name="Default",
        bindings=[
            TabletBinding(button_id=1, action_kind="set_tool",
                          params={"tool": "brush"}, label="Stylus tip"),
            TabletBinding(button_id=2, action_kind="set_tool",
                          params={"tool": "eraser"}, label="Eraser end"),
            TabletBinding(button_id=3, action_kind="undo",
                          label="Side button A"),
            TabletBinding(button_id=4, action_kind="redo",
                          label="Side button B"),
        ],
    ),
    TabletProfile(
        name="Painter",
        bindings=[
            TabletBinding(button_id=1, action_kind="set_tool",
                          params={"tool": "brush"}, label="Stylus tip"),
            TabletBinding(button_id=2, action_kind="eyedropper",
                          label="Eraser end (sample)"),
            TabletBinding(button_id=3, action_kind="undo",
                          label="Side button A"),
            TabletBinding(button_id=4, action_kind="toggle_panel",
                          params={"panel": "color"}, label="Side button B"),
        ],
    ),
)


def find_built_in(name: str) -> TabletProfile | None:
    for profile in BUILT_IN_PROFILES:
        if profile.name == name:
            return profile
    return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_profiles(profiles: list[TabletProfile]) -> None:
    if len(profiles) > MAX_PROFILES:
        raise ValueError(
            f"refusing to save {len(profiles)} profiles, max is {MAX_PROFILES}",
        )
    user_setting_dict[_USER_SETTING_KEY] = [p.to_dict() for p in profiles]
    schedule_save()


def load_profiles() -> list[TabletProfile]:
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[TabletProfile] = []
    for entry in raw:
        try:
            out.append(TabletProfile.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return out


def all_profiles() -> list[TabletProfile]:
    return list(BUILT_IN_PROFILES) + load_profiles()
