"""Unit tests for the desktop pet's built-in integration controller (hotkeys) and registry.

The controller is built against a fake host + a monkeypatched fake client, so
the configure / signal-routing logic is verified without pynput or a widget.
The OBS / Twitch / webhook / notification controllers are the Desktop Pet
Integrations plugin's (``test_pet_integrations_controllers``).
"""
from __future__ import annotations

from _pet_fakes import FakeHost, FakeSignal

from Imervue.desktop_pet import pet_features
from Imervue.desktop_pet.hotkey_manager import DEFAULT_HOTKEY_BINDINGS
from Imervue.desktop_pet.pet_features import (
    HotkeyController,
    build_integration_controllers,
)


# ---------------------------------------------------------------
# Hotkeys
# ---------------------------------------------------------------


class _FakeHotkeys:
    def __init__(self, parent=None) -> None:
        self.action_triggered = FakeSignal()
        self.bindings: dict | None = None
        self._running = False

    def set_bindings(self, bindings) -> None:
        self.bindings = bindings

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running


def test_hotkeys_uses_persisted_bindings_by_default(monkeypatch):
    monkeypatch.setattr(pet_features, "GlobalHotkeyManager", _FakeHotkeys)
    first_action = next(iter(DEFAULT_HOTKEY_BINDINGS))
    host = FakeHost({"hotkeys": {first_action: "ctrl+alt+z"}})
    ctl = HotkeyController(host)
    assert ctl.set_enabled(True) is True
    assert ctl._client.bindings[first_action] == "ctrl+alt+z"   # noqa: SLF001
    assert host.persisted == {"hotkeys_enabled": True}


def test_hotkeys_explicit_bindings_override_settings(monkeypatch):
    monkeypatch.setattr(pet_features, "GlobalHotkeyManager", _FakeHotkeys)
    ctl = HotkeyController(FakeHost())
    ctl.set_enabled(True, {"toggle_visible": "f8"})
    assert ctl._client.bindings == {"toggle_visible": "f8"}   # noqa: SLF001


def test_hotkeys_disable_persists_false(monkeypatch):
    monkeypatch.setattr(pet_features, "GlobalHotkeyManager", _FakeHotkeys)
    host = FakeHost()
    ctl = HotkeyController(host)
    ctl.set_enabled(True)
    assert ctl.set_enabled(False) is True
    assert host.persisted == {"hotkeys_enabled": False}


# ---------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------


def test_build_registry_holds_the_built_in_hotkeys_only():
    """The OBS / Twitch / webhook / notification ones come from a plugin (add_integration)."""
    registry = build_integration_controllers(FakeHost())
    assert set(registry) == {"hotkeys"}


# ---------------------------------------------------------------
# Integrations a plugin adds to the pet
# ---------------------------------------------------------------


class _Recorder:
    def __init__(self) -> None:
        self.shut = 0

    def shutdown(self) -> None:
        self.shut += 1


def _registry_owner():
    """The three registry methods of ``PetWindow`` on a plain object (no GL window)."""
    from types import SimpleNamespace

    from Imervue.desktop_pet.pet_window import PetWindow
    owner = SimpleNamespace(_features={})
    owner.remove_integration = lambda key: PetWindow.remove_integration(owner, key)
    owner.add_integration = lambda key, ctl: PetWindow.add_integration(owner, key, ctl)
    owner.integration = lambda key: PetWindow.integration(owner, key)
    return owner


def test_a_plugin_integration_joins_the_registry_shutdown_stops():
    owner = _registry_owner()
    first = _Recorder()
    owner.add_integration("obs", first)
    assert owner.integration("obs") is first
    assert owner._features == {"obs": first}   # noqa: SLF001 - what shutdown() walks


def test_adding_under_a_taken_key_stops_the_old_one():
    owner = _registry_owner()
    first, second = _Recorder(), _Recorder()
    owner.add_integration("obs", first)
    owner.add_integration("obs", second)
    assert first.shut == 1
    assert owner.integration("obs") is second


def test_removing_stops_it_and_forgets_it():
    owner = _registry_owner()
    ctl = _Recorder()
    owner.add_integration("webhook", ctl)
    owner.remove_integration("webhook")
    owner.remove_integration("webhook")      # unknown key: nothing to do
    assert ctl.shut == 1
    assert owner.integration("webhook") is None
