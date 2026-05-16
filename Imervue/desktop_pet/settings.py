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
"""Single top-level slot in :data:`user_setting_dict` that owns
every persisted desktop-pet field. Grouping under one key keeps
the settings file tidy + means profile switches move all pet
state at once."""

# Sensible defaults — each key documents the value type / semantic
# range. The window / workspace read these on construction and
# write them back as the user mutates state.
DEFAULTS: dict[str, Any] = {
    "last_rig_path": "",          # absolute path; "" = no rig loaded
    "position": [-1, -1],         # screen x and y; both negative means "use default"
    "size_preset": "medium",      # "small" | "medium" | "large"
    "opacity": 1.0,               # 0.1 - 1.0
    "click_through": False,
    "anchor_locked": False,       # disable drag-to-move
    "always_on_bottom": False,    # desktop-widget mode (mutually exclusive with top)
    "hide_on_fullscreen": True,
    "snap_threshold": 24,         # px
    "drivers": {
        "auto_idle": False,
        "idle_motion": False,
        "auto_blink": False,
        "drag_track": False,
        "mic_lipsync": False,
        "webcam_tracking": False,
    },
    "show_on_launch": False,      # auto-show the pet when Imervue starts
    "speech_enabled": True,       # let the speech bubble pop on clicks
    "script_path": "",            # path to a user-supplied .petscript.json; "" = built-in defaults
}


def load() -> dict[str, Any]:
    """Return the current persisted settings, merged with defaults
    so older settings files (missing keys we added later) still
    produce a complete dict."""
    raw = user_setting_dict.get(SETTINGS_KEY)
    if not isinstance(raw, dict):
        return _deep_copy_defaults()
    out = _deep_copy_defaults()
    _merge_into(out, raw)
    return _clamped(out)


def save(settings: dict[str, Any]) -> None:
    """Write ``settings`` back into :data:`user_setting_dict` —
    callers should mutate the dict returned by :func:`load` and
    pass it back. Unknown keys are kept (so a future-version
    settings file round-trips), known keys are validated /
    clamped."""
    if not isinstance(settings, dict):
        logger.warning("desktop-pet settings must be a dict, got %s", type(settings))
        return
    user_setting_dict[SETTINGS_KEY] = _clamped(settings)


def update(**fields: Any) -> dict[str, Any]:
    """Convenience: load → mutate the listed fields → save → return
    the new state. Lets callers do
    ``settings.update(opacity=0.8)`` instead of a 4-line read /
    mutate / write dance."""
    current = load()
    _merge_into(current, fields)
    save(current)
    return current


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
    return out
