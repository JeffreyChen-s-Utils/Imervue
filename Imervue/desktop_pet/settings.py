"""Desktop-pet settings persistence.

A thin layer over ``user_setting_dict["desktop_pet"]`` that
documents the schema, supplies defaults, and validates / clamps
values on load. The pet window and workspace both consult /
mutate this so the user's "last state" — position, opacity, which
drivers were running, where on screen, which rig was loaded — is
restored on the next Imervue launch.

The schema is intentionally simple key-value JSON-safe — every
write flushes through the existing user-settings save path so the
desktop pet inherits the global multi-profile / autosave story.
"""
from __future__ import annotations

import logging
from typing import Any

from Imervue.user_settings.user_setting_dict import user_setting_dict

logger = logging.getLogger("Imervue.desktop_pet.settings")

SETTINGS_KEY = "desktop_pet"
"""Top-level slot in :data:`user_setting_dict` for the *primary*
pet's settings. Kept verbatim for backwards compatibility — single-
pet users see no schema change, and the legacy
:func:`load` / :func:`save` / :func:`update` calls (with no
``pet_id`` argument) still read / write this key."""

EXTRAS_KEY = "desktop_pet_extras"
"""Sibling slot holding additional pet slices keyed by pet id —
``{pet_id: <settings dict>, ...}``. The primary pet always has
:data:`DEFAULT_PET_ID`; extras have arbitrary stable string ids."""

DEFAULT_PET_ID: str = "default"
"""The primary pet's id. Reserved — it always maps to
:data:`SETTINGS_KEY`, never to a slot under :data:`EXTRAS_KEY`."""

# Sensible defaults — each key documents the value type / semantic
# range. The window / workspace read these on construction and
# write them back as the user mutates state.
DEFAULTS: dict[str, Any] = {
    "last_rig_path": "",          # absolute path; "" = no rig loaded
    "position": [-1, -1],         # screen x and y; both negative means "use default"
    "screen_name": "",            # QScreen.name() the pet was last on; "" = "no preference"
    "size_preset": "medium",      # "small" | "medium" | "large"
    "opacity": 1.0,               # 0.1 - 1.0
    "click_through": False,
    "anchor_locked": False,       # disable drag-to-move
    "always_on_bottom": False,    # desktop-widget mode (mutually exclusive with top)
    "hide_on_fullscreen": True,
    "snap_threshold": 24,         # px
    "drivers": {
        # Three zero-dep drivers are on by default so a fresh
        # install shows a *moving* pet rather than a static figure
        # — breathing + drift, random idle motion turnover, and
        # natural blinking are all character-feeling effects that
        # any rig benefits from.
        "auto_idle": True,
        "idle_motion": True,
        "auto_blink": True,
        # The remaining drivers either need a heavy optional dep
        # (sounddevice, opencv-python, pynput, pyvirtualcam) or
        # explicit user intent (drag-track + mouse-gaze move the
        # head every tick, which some users find distracting). Stay
        # off by default; the user opts in via the workspace tab.
        "drag_track": False,
        "mouse_gaze": False,
        "mic_lipsync": False,
        "webcam_tracking": False,
        "music_rhythm": False,
        "idle_minigame": False,
    },
    "show_on_launch": False,      # auto-show the pet when Imervue starts
    "speech_enabled": True,       # let the speech bubble pop on clicks
    "script_path": "",            # path to a user-supplied .petscript.json; "" = built-in defaults
    "hotkeys_enabled": False,     # global keyboard shortcuts (needs pynput)
    "hotkeys": {},                # {action: "ctrl+shift+p"}; empty = use module defaults
    "obs_enabled": False,         # listen for OBS events (needs obs-websocket-py)
    "obs_host": "localhost",
    "obs_port": 4455,
    "obs_password": "",
    "twitch_enabled": False,      # listen for Twitch chat keywords
    "twitch_channel": "",         # channel to join (omit leading #)
    "twitch_oauth": "",           # oauth:xxx token from twitchapps.com/tmi
    "twitch_triggers": {},        # {keyword: motion-group-name}
    "virtual_camera_enabled": False,   # stream pet to system virtual camera (needs pyvirtualcam)
    "llm_enabled": False,              # use a local LLM for fresh speech lines
    "llm_base_url": "http://localhost:11434",
    "llm_model": "llama3.2:1b",
    "llm_persona": "",                 # empty = use module default persona
    "win_notifications_enabled": False,   # react to Windows toast notifications (needs winrt)
    "win_notifications_ignored": [],      # list of app_user_model_ids to ignore
    "click_sfx_enabled": False,           # play sound effects on click / drag / drop / notify
    "click_sfx_volume": 0.6,              # 0.0 - 1.0
    "click_sfx_paths": {},                # {event: path}; events without entries stay silent
    "pet_shadow_enabled": True,           # render a soft drop shadow under the puppet
    "pet_shadow_opacity": 0.7,            # 0.0 - 1.0 multiplier on the texture's built-in falloff
    "pet_shadow_scale": 1.0,              # 0.0 - 2.0 width-of-shadow multiplier
    "webhook_enabled": False,             # localhost HTTP server for external triggers
    "webhook_port": 9876,                 # listen port (loopback only)
    "webhook_token": "",                  # optional bearer token; empty = no auth
}


def load(pet_id: str = DEFAULT_PET_ID) -> dict[str, Any]:
    """Return the persisted settings for ``pet_id``, merged with
    defaults so older settings files (missing keys we added later)
    still produce a complete dict.

    Passing :data:`DEFAULT_PET_ID` (the default) reads / writes the
    primary pet slot at :data:`SETTINGS_KEY`; any other id reads
    from the ``desktop_pet_extras`` sub-dict. The pet window's
    constructor calls this with its own id."""
    raw = _read_raw_slot(pet_id)
    if not isinstance(raw, dict):
        return _deep_copy_defaults()
    out = _deep_copy_defaults()
    _merge_into(out, raw)
    return _clamped(out)


def save(settings: dict[str, Any], pet_id: str = DEFAULT_PET_ID) -> None:
    """Write ``settings`` back to ``pet_id``'s slot. Callers should
    mutate the dict returned by :func:`load` and pass it back.
    Unknown keys are kept (forward-compat round-trip); known keys
    are validated / clamped."""
    if not isinstance(settings, dict):
        logger.warning("desktop-pet settings must be a dict, got %s", type(settings))
        return
    _write_raw_slot(pet_id, _clamped(settings))


def update(pet_id: str = DEFAULT_PET_ID, /, **fields: Any) -> dict[str, Any]:
    """Convenience: load → mutate the listed fields → save → return
    the new state for ``pet_id``. ``pet_id`` is positional-only so
    legacy calls (``settings.update(opacity=0.8)``) keep working —
    no field is named ``pet_id``, so there's no risk of collision."""
    current = load(pet_id)
    _merge_into(current, fields)
    save(current, pet_id)
    return current


def list_pet_ids() -> list[str]:
    """Return every pet id with persisted settings: the primary
    (:data:`DEFAULT_PET_ID`) first, then any extras in insertion
    order. The primary always appears even if its slot is empty —
    callers want a deterministic baseline pet to spawn."""
    out: list[str] = [DEFAULT_PET_ID]
    extras = user_setting_dict.get(EXTRAS_KEY)
    if isinstance(extras, dict):
        for key in extras:
            if isinstance(key, str) and key and key != DEFAULT_PET_ID:
                out.append(key)
    return out


def add_pet(pet_id: str) -> dict[str, Any]:
    """Create a new pet slot under ``pet_id`` (must differ from
    :data:`DEFAULT_PET_ID`) and return its freshly-defaulted
    settings dict. No-op when the slot already exists — the caller
    just gets the existing slot back."""
    if not pet_id or pet_id == DEFAULT_PET_ID:
        raise ValueError(
            f"pet_id must be a non-empty string distinct from "
            f"{DEFAULT_PET_ID!r}, got {pet_id!r}",
        )
    extras = user_setting_dict.get(EXTRAS_KEY)
    if not isinstance(extras, dict):
        extras = {}
    if pet_id not in extras:
        extras[pet_id] = _deep_copy_defaults()
        user_setting_dict[EXTRAS_KEY] = extras
    return load(pet_id)


def remove_pet(pet_id: str) -> bool:
    """Delete ``pet_id``'s extras slot. The primary pet
    (:data:`DEFAULT_PET_ID`) cannot be removed — returning
    ``False`` rather than raising so a misclick on the workspace's
    "remove" button doesn't crash the app. Returns ``True`` when
    a slot was actually deleted."""
    if pet_id == DEFAULT_PET_ID:
        return False
    extras = user_setting_dict.get(EXTRAS_KEY)
    if not isinstance(extras, dict) or pet_id not in extras:
        return False
    del extras[pet_id]
    user_setting_dict[EXTRAS_KEY] = extras
    return True


def _read_raw_slot(pet_id: str) -> Any:
    if pet_id == DEFAULT_PET_ID:
        return user_setting_dict.get(SETTINGS_KEY)
    extras = user_setting_dict.get(EXTRAS_KEY)
    if not isinstance(extras, dict):
        return None
    return extras.get(pet_id)


def _write_raw_slot(pet_id: str, value: dict[str, Any]) -> None:
    if pet_id == DEFAULT_PET_ID:
        user_setting_dict[SETTINGS_KEY] = value
        return
    extras = user_setting_dict.get(EXTRAS_KEY)
    if not isinstance(extras, dict):
        extras = {}
    extras[pet_id] = value
    user_setting_dict[EXTRAS_KEY] = extras


# ---------------------------------------------------------------
# Internals
# ---------------------------------------------------------------


def _deep_copy_defaults() -> dict[str, Any]:
    """``copy.deepcopy(DEFAULTS)`` would work but is overkill for
    a two-level dict with primitive values. Hand-roll it so the
    helper is import-light and easy to audit."""
    out: dict[str, Any] = {}
    for key, value in DEFAULTS.items():
        if isinstance(value, dict):
            out[key] = dict(value)
        elif isinstance(value, list):
            out[key] = list(value)
        else:
            out[key] = value
    return out


def _merge_into(target: dict[str, Any], source: dict[str, Any]) -> None:
    """One-level-deep merge — top-level keys overwrite, nested
    dicts (``drivers``) merge so an older settings file that
    doesn't know about a new driver still gets the new
    driver's default."""
    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
        ):
            target[key].update(value)
        else:
            target[key] = value


def _clamped(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate / clamp ranges so a corrupted settings file can't
    crash the pet on next launch. Anything out-of-spec gets
    reset to its default."""
    out = dict(settings)
    # Opacity: 0.1 minimum so the pet never becomes fully
    # invisible-and-unfindable; 1.0 maximum is physical.
    try:
        opacity = float(out.get("opacity", DEFAULTS["opacity"]))
    except (TypeError, ValueError):
        opacity = DEFAULTS["opacity"]
    out["opacity"] = max(0.1, min(1.0, opacity))
    # Snap threshold: 0 (disabled) up to 200 px (very sticky).
    try:
        snap = int(out.get("snap_threshold", DEFAULTS["snap_threshold"]))
    except (TypeError, ValueError):
        snap = DEFAULTS["snap_threshold"]
    out["snap_threshold"] = max(0, min(200, snap))
    # Size preset: known string or fall back.
    if out.get("size_preset") not in ("small", "medium", "large"):
        out["size_preset"] = DEFAULTS["size_preset"]
    # Position must be a 2-element list of ints; -1 means "no
    # saved position".
    pos = out.get("position")
    if (
        not isinstance(pos, (list, tuple))
        or len(pos) != 2
        or not all(isinstance(v, (int, float)) for v in pos)
    ):
        out["position"] = list(DEFAULTS["position"])
    else:
        out["position"] = [int(pos[0]), int(pos[1])]
    # Booleans coerce.
    for bool_key in (
        "click_through", "anchor_locked", "always_on_bottom",
        "hide_on_fullscreen", "show_on_launch", "speech_enabled",
    ):
        out[bool_key] = bool(out.get(bool_key, DEFAULTS[bool_key]))
    # Drivers sub-dict — coerce each entry; ignore unknown keys
    # (forward-compat: future versions may add new ones).
    drivers = out.get("drivers")
    if not isinstance(drivers, dict):
        drivers = dict(DEFAULTS["drivers"])
    else:
        for driver in DEFAULTS["drivers"]:
            drivers[driver] = bool(drivers.get(driver, False))
    out["drivers"] = drivers
    # Strings.
    if not isinstance(out.get("last_rig_path"), str):
        out["last_rig_path"] = ""
    if not isinstance(out.get("script_path"), str):
        out["script_path"] = ""
    if not isinstance(out.get("screen_name"), str):
        out["screen_name"] = ""
    return out
