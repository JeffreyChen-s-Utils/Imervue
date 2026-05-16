"""Tests for the desktop-pet settings persistence helper.

The helper layers over ``user_setting_dict["desktop_pet"]`` and
must:

* return a full default dict on a missing entry;
* merge a partial saved dict with defaults so older settings
  files don't lose keys we add later;
* clamp out-of-range numeric values + reset garbage strings to
  their defaults so a corrupted file can't crash the pet;
* round-trip a saved dict through load() unchanged.

The autouse ``_isolate_user_settings`` fixture (tests/conftest.py)
points ``user_setting_dict`` at a tmp file per test, so mutations
made here can't leak into the real user settings.
"""
from __future__ import annotations

from Imervue.desktop_pet import settings as pet_settings
from Imervue.user_settings.user_setting_dict import user_setting_dict


def test_load_returns_defaults_when_unset():
    """No saved entry → load() yields every key from
    ``DEFAULTS`` with the documented default value. Catches the
    bug where load() returns an empty dict and downstream code
    KeyErrors on first launch."""
    user_setting_dict.pop("desktop_pet", None)
    state = pet_settings.load()
    assert state["last_rig_path"] == ""
    assert state["size_preset"] == "medium"
    assert state["opacity"] == 1.0
    assert state["click_through"] is False
    assert state["anchor_locked"] is False
    assert isinstance(state["drivers"], dict)
    assert "auto_idle" in state["drivers"]


def test_save_then_load_round_trips():
    pet_settings.save({
        "last_rig_path": "examples/puppet/march_7th.puppet",
        "size_preset": "large",
        "opacity": 0.7,
        "click_through": True,
        "anchor_locked": False,
        "always_on_bottom": False,
        "hide_on_fullscreen": True,
        "snap_threshold": 32,
        "drivers": {"auto_idle": True, "auto_blink": True},
        "show_on_launch": True,
        "speech_enabled": False,
        "position": [120, 240],
    })
    state = pet_settings.load()
    assert state["last_rig_path"] == "examples/puppet/march_7th.puppet"
    assert state["size_preset"] == "large"
    assert state["opacity"] == 0.7
    assert state["click_through"] is True
    assert state["snap_threshold"] == 32
    assert state["drivers"]["auto_idle"] is True
    assert state["drivers"]["auto_blink"] is True
    # Unspecified driver still defaults to False.
    assert state["drivers"]["mic_lipsync"] is False
    assert state["show_on_launch"] is True
    assert state["speech_enabled"] is False
    assert state["position"] == [120, 240]


def test_opacity_clamps_below_minimum():
    """Opacity 0 would make the pet completely invisible — the
    user might toggle it from the settings file and lose the
    ability to find their pet. Clamp to 0.1 as the floor."""
    pet_settings.save({"opacity": 0.0})
    assert pet_settings.load()["opacity"] == 0.1


def test_opacity_clamps_above_maximum():
    pet_settings.save({"opacity": 5.0})
    assert pet_settings.load()["opacity"] == 1.0


def test_opacity_garbage_falls_back_to_default():
    """A corrupted settings file could write a string into
    opacity; load() must coerce or fall back rather than crash."""
    pet_settings.save({"opacity": "not a number"})
    assert pet_settings.load()["opacity"] == 1.0


def test_snap_threshold_clamps():
    pet_settings.save({"snap_threshold": -50})
    assert pet_settings.load()["snap_threshold"] == 0
    pet_settings.save({"snap_threshold": 500})
    assert pet_settings.load()["snap_threshold"] == 200


def test_size_preset_garbage_falls_back():
    """Only the three known preset strings are valid; anything
    else (typo, future-version preset) gets coerced back to
    the default."""
    pet_settings.save({"size_preset": "huge"})
    assert pet_settings.load()["size_preset"] == "medium"


def test_position_garbage_falls_back():
    pet_settings.save({"position": "off-screen"})
    assert pet_settings.load()["position"] == [-1, -1]
    pet_settings.save({"position": [10]})
    assert pet_settings.load()["position"] == [-1, -1]


def test_position_floats_coerce_to_ints():
    pet_settings.save({"position": [120.4, 240.9]})
    assert pet_settings.load()["position"] == [120, 240]


def test_drivers_merge_keeps_unknown_keys_for_forward_compat():
    """A future version may add new drivers; older settings
    files with the new key shouldn't lose it on round-trip."""
    pet_settings.save({"drivers": {"auto_idle": True, "future_driver_x": True}})
    state = pet_settings.load()
    assert state["drivers"]["auto_idle"] is True
    # Future driver passed through.
    assert state["drivers"].get("future_driver_x") is True


def test_update_helper_writes_through():
    """``update(**fields)`` is the load → mutate → save shortcut
    every workspace setter uses; verify it actually persists."""
    pet_settings.save({"opacity": 1.0})
    pet_settings.update(opacity=0.5)
    assert pet_settings.load()["opacity"] == 0.5


def test_save_ignores_non_dict():
    """A buggy caller passing None / a list to save() must not
    overwrite the persisted state with garbage — silently
    ignore the call and keep what was there."""
    pet_settings.save({"opacity": 0.6})
    pet_settings.save(None)   # type: ignore[arg-type]
    assert pet_settings.load()["opacity"] == 0.6
