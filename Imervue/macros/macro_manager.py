"""
Macro recording / replay.

Design
------
- ``MacroManager`` is a module-level singleton (``manager``) holding recording
  state plus saved macros (persisted via ``user_setting_dict``).
- During recording, actions call ``manager.record("action_id", **kwargs)``.
  Only actions present in :data:`ACTION_REGISTRY` are captured.
- Replay iterates the saved steps and invokes each action's callable on the
  provided selection. Each action handler is responsible for validating its
  own kwargs — the manager does not introspect them.

Keeping the registry explicit (rather than ad-hoc callbacks) means replay is
safe to deserialize from JSON without executing arbitrary code.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, TYPE_CHECKING

from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.macros")

_SETTINGS_KEY = "macros"
_LAST_KEY = "macro_last_name"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MacroStep:
    """One recorded action: an ID from ACTION_REGISTRY plus JSON-safe kwargs."""
    action: str
    kwargs: dict


@dataclass
class Macro:
    name: str
    steps: list[MacroStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "steps": [{"action": s.action, "kwargs": s.kwargs} for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Macro | None:
        if not isinstance(data, dict):
            return None
        name = data.get("name")
        steps_raw = data.get("steps", [])
        if not isinstance(name, str) or not isinstance(steps_raw, list):
            return None
        steps: list[MacroStep] = []
        for item in steps_raw:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            kwargs = item.get("kwargs", {})
            if isinstance(action, str) and isinstance(kwargs, dict):
                steps.append(MacroStep(action=action, kwargs=dict(kwargs)))
        created_at = data.get("created_at", time.time())
        if not isinstance(created_at, (int, float)):
            created_at = time.time()
        return cls(name=name, steps=steps, created_at=float(created_at))


# ---------------------------------------------------------------------------
# Action registry — dispatchers for replay
# ---------------------------------------------------------------------------

ReplayFunc = Callable[["ImervueMainWindow", Iterable[str], dict], None]


def _replay_set_rating(_ui, paths, kwargs) -> None:
    rating = int(kwargs.get("rating", 0))
    if not 0 <= rating <= 5:
        return
    ratings = user_setting_dict.get("image_ratings", {})
    for path in paths:
        if rating == 0:
            ratings.pop(path, None)
        else:
            ratings[path] = rating
    user_setting_dict["image_ratings"] = ratings
    schedule_save()


def _replay_toggle_favorite(_ui, paths, kwargs) -> None:
    desired = kwargs.get("value")  # True/False/None (toggle each)
    favorites = set(user_setting_dict.get("image_favorites", []))
    for path in paths:
        if desired is True:
            favorites.add(path)
        elif desired is False:
            favorites.discard(path)
        elif path in favorites:
            favorites.discard(path)
        else:
            favorites.add(path)
    user_setting_dict["image_favorites"] = list(favorites)
    schedule_save()


def _replay_set_color(_ui, paths, kwargs) -> None:
    from Imervue.user_settings.color_labels import set_color_label
    color = kwargs.get("color")
    for path in paths:
        set_color_label(path, color)


def _replay_add_tag(_ui, paths, kwargs) -> None:
    from Imervue.user_settings.tags import add_tag
    tag = kwargs.get("tag")
    if not isinstance(tag, str) or not tag:
        return
    for path in paths:
        add_tag(tag, path)


def _replay_remove_tag(_ui, paths, kwargs) -> None:
    from Imervue.user_settings.tags import remove_tag
    tag = kwargs.get("tag")
    if not isinstance(tag, str) or not tag:
        return
    for path in paths:
        remove_tag(tag, path)


ACTION_REGISTRY: dict[str, ReplayFunc] = {
    "set_rating": _replay_set_rating,
    "toggle_favorite": _replay_toggle_favorite,
    "set_color": _replay_set_color,
    "add_tag": _replay_add_tag,
    "remove_tag": _replay_remove_tag,
}


# ---------------------------------------------------------------------------
# Manager (module singleton)
# ---------------------------------------------------------------------------

class MacroManager:
    def __init__(self) -> None:
        self._recording: list[MacroStep] | None = None

    # -- recording state --------------------------------------------------
    def is_recording(self) -> bool:
        return self._recording is not None

    def start_recording(self) -> None:
        self._recording = []

    def cancel_recording(self) -> None:
        self._recording = None

    def stop_recording(self, name: str) -> Macro | None:
        """Finalise the current recording under ``name``. None if nothing to save."""
        if self._recording is None:
            return None
        steps = self._recording
        self._recording = None
        if not steps:
            return None
        macro = Macro(name=name, steps=steps)
        self._persist(macro)
        user_setting_dict[_LAST_KEY] = name
        schedule_save()
        return macro

    def record(self, action: str, **kwargs) -> None:
        """Append a step to the running recording (no-op if not recording)."""
        if self._recording is None:
            return
        if action not in ACTION_REGISTRY:
            logger.debug("Ignoring unknown macro action: %s", action)
            return
        self._recording.append(MacroStep(action=action, kwargs=dict(kwargs)))

    # -- persistence ------------------------------------------------------
    def _persist(self, macro: Macro) -> None:
        macros = self._load_all()
        # Replace existing macro with the same name.
        macros = [m for m in macros if m.name != macro.name]
        macros.append(macro)
        user_setting_dict[_SETTINGS_KEY] = [m.to_dict() for m in macros]
        schedule_save()

    def _load_all(self) -> list[Macro]:
        raw = user_setting_dict.get(_SETTINGS_KEY, [])
        if not isinstance(raw, list):
            return []
        out: list[Macro] = []
        for item in raw:
            macro = Macro.from_dict(item)
            if macro is not None:
                out.append(macro)
        return out

    def list_macros(self) -> list[Macro]:
        return self._load_all()

    def delete_macro(self, name: str) -> None:
        macros = [m for m in self._load_all() if m.name != name]
        user_setting_dict[_SETTINGS_KEY] = [m.to_dict() for m in macros]
        schedule_save()

    def get_macro(self, name: str) -> Macro | None:
        for macro in self._load_all():
            if macro.name == name:
                return macro
        return None

    # -- replay -----------------------------------------------------------
    def replay(self, ui: ImervueMainWindow, macro: Macro, paths: Iterable[str]) -> int:
        """Apply ``macro`` to ``paths``. Returns the number of steps executed."""
        path_list = list(paths)
        if not path_list:
            return 0
        executed = 0
        for step in macro.steps:
            func = ACTION_REGISTRY.get(step.action)
            if func is None:
                continue
            try:
                func(ui, path_list, step.kwargs)
                executed += 1
            except Exception as exc:  # noqa: BLE001 - replay must not kill UI
                logger.error("Macro step %s failed: %s", step.action, exc)
        return executed


manager = MacroManager()


# ---------------------------------------------------------------------------
# Convenience entry points used by menu actions / shortcuts
# ---------------------------------------------------------------------------

def _current_selection(ui: ImervueMainWindow) -> list[str]:
    """Return selected image paths, falling back to the current image."""
    viewer = getattr(ui, "viewer", None)
    if viewer is None:
        return []
    selected = getattr(viewer, "selected_tiles", None)
    if isinstance(selected, (set, list)) and selected:
        return [p for p in selected if isinstance(p, str)]
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        return [images[idx]]
    return []


def replay_last_macro(ui: ImervueMainWindow) -> bool:
    """Replay the most-recently saved macro against the current selection."""
    last = user_setting_dict.get(_LAST_KEY)
    if not isinstance(last, str) or not last:
        _toast(ui, "macro_no_last", "No macro to replay")
        return False
    macro = manager.get_macro(last)
    if macro is None:
        _toast(ui, "macro_no_last", "No macro to replay")
        return False
    paths = _current_selection(ui)
    if not paths:
        _toast(ui, "macro_no_selection", "No images selected")
        return False
    count = manager.replay(ui, macro, paths)
    _toast(
        ui,
        "macro_replayed",
        "Replayed {name}: {count} step(s) on {files} file(s)",
        name=macro.name, count=count, files=len(paths),
    )
    return True


def _toast(ui, key: str, fallback: str, **fmt) -> None:
    if not hasattr(ui, "toast"):
        return
    from Imervue.multi_language.language_wrapper import language_wrapper
    lang = language_wrapper.language_word_dict
    try:
        ui.toast.info(lang.get(key, fallback).format(**fmt))
    except (KeyError, IndexError, ValueError):
        ui.toast.info(fallback)
