"""Unit tests for the desktop-pet integration feature controllers.

Each controller is built against a fake host + a monkeypatched fake
client so the configure / signal-routing logic is verified without a
real websocket / socket / WinRT dependency or any Qt widget.
"""
from __future__ import annotations

from Imervue.desktop_pet import pet_features
from Imervue.desktop_pet.hotkey_manager import DEFAULT_HOTKEY_BINDINGS
from Imervue.desktop_pet.pet_features import (
    HotkeyController,
    ObsHookController,
    TwitchHookController,
    WebhookController,
    WindowsNotificationController,
    build_integration_controllers,
)


class _Signal:
    def __init__(self) -> None:
        self.slots: list = []

    def connect(self, slot) -> None:
        self.slots.append(slot)

    def emit(self, *args) -> None:
        for slot in self.slots:
            slot(*args)


class _FakeHost:
    def __init__(self, settings: dict | None = None) -> None:
        self.persisted: dict = {}
        self._settings = settings or {}
        self.played: list[str] = []
        self.spoken: list[str] = []
        self.notified: list[str] = []
        self.hotkey_actions: list[str] = []
        self.speech_on = True

    def on_hotkey_action(self, action: str) -> None:
        self.hotkey_actions.append(action)

    def persist(self, **fields: object) -> None:
        self.persisted.update(fields)

    def setting(self, key: str, default: object) -> object:
        return self._settings.get(key, default)

    def play_group(self, group: str) -> bool:
        self.played.append(group)
        return True

    def speak(self, line: str) -> None:
        self.spoken.append(line)

    def speak_notification(self, line: str) -> None:
        self.notified.append(line)


# ---------------------------------------------------------------
# OBS
# ---------------------------------------------------------------


class _FakeObs:
    def __init__(self, parent=None) -> None:
        self.group_triggered = _Signal()
        self.endpoint: dict | None = None
        self._running = False

    def set_endpoint(self, **kwargs) -> None:
        self.endpoint = kwargs

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running


def test_obs_configures_endpoint_from_settings(monkeypatch):
    monkeypatch.setattr(pet_features, "ObsEventClient", _FakeObs)
    host = _FakeHost({"obs_host": "h", "obs_port": 9, "obs_password": "p"})
    ctl = ObsHookController(host)
    ctl.set_enabled(True)
    assert ctl._client.endpoint == {"host": "h", "port": 9, "password": "p"}   # noqa: SLF001
    assert host.persisted == {"obs_enabled": True}


def test_obs_group_signal_routes_to_play(monkeypatch):
    monkeypatch.setattr(pet_features, "ObsEventClient", _FakeObs)
    host = _FakeHost()
    ctl = ObsHookController(host)
    ctl.set_enabled(True)
    ctl._client.group_triggered.emit("Wave")   # noqa: SLF001
    assert host.played == ["Wave"]


# ---------------------------------------------------------------
# Twitch
# ---------------------------------------------------------------


class _FakeTwitch:
    def __init__(self, parent=None) -> None:
        self.keyword_matched = _Signal()
        self.endpoint: dict | None = None
        self.triggers: dict | None = None
        self._running = False

    def set_endpoint(self, **kwargs) -> None:
        self.endpoint = kwargs

    def set_triggers(self, triggers) -> None:
        self.triggers = triggers

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running


def test_twitch_configures_endpoint_and_triggers(monkeypatch):
    monkeypatch.setattr(pet_features, "TwitchChatClient", _FakeTwitch)
    host = _FakeHost({
        "twitch_channel": "chan", "twitch_oauth": "tok",
        "twitch_triggers": {"hi": "Wave"},
    })
    ctl = TwitchHookController(host)
    ctl.set_enabled(True)
    assert ctl._client.endpoint == {"channel": "chan", "oauth": "tok"}   # noqa: SLF001
    assert ctl._client.triggers == {"hi": "Wave"}   # noqa: SLF001


# ---------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------


class _FakeWebhook:
    def __init__(self, parent=None) -> None:
        self.command_received = _Signal()
        self.endpoint: dict | None = None
        self._running = False

    def set_endpoint(self, **kwargs) -> None:
        self.endpoint = kwargs

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running


def test_webhook_command_routes_motion_and_speech(monkeypatch):
    monkeypatch.setattr(pet_features, "WebhookReceiver", _FakeWebhook)
    host = _FakeHost()
    ctl = WebhookController(host)
    ctl.set_enabled(True)
    ctl._client.command_received.emit("Dance", "hello")   # noqa: SLF001
    assert host.played == ["Dance"]
    assert host.spoken == ["hello"]


def test_webhook_command_speech_suppressed_when_speech_off(monkeypatch):
    monkeypatch.setattr(pet_features, "WebhookReceiver", _FakeWebhook)
    host = _FakeHost()
    host.speech_on = False
    ctl = WebhookController(host)
    ctl.set_enabled(True)
    ctl._client.command_received.emit("Dance", "hello")   # noqa: SLF001
    assert host.played == ["Dance"]
    assert host.spoken == []


def test_webhook_command_motion_only(monkeypatch):
    monkeypatch.setattr(pet_features, "WebhookReceiver", _FakeWebhook)
    host = _FakeHost()
    ctl = WebhookController(host)
    ctl.set_enabled(True)
    ctl._client.command_received.emit("", "just talk")   # noqa: SLF001
    assert host.played == []
    assert host.spoken == ["just talk"]


# ---------------------------------------------------------------
# Windows notifications
# ---------------------------------------------------------------


class _FakeNotifier:
    def __init__(self, parent=None) -> None:
        self.action_triggered = _Signal()
        self.speech_triggered = _Signal()
        self.ignored: tuple = ()
        self._running = False

    def set_ignored_app_ids(self, ids) -> None:
        self.ignored = ids

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running


def test_notifications_sanitize_ignored_ids(monkeypatch):
    monkeypatch.setattr(
        pet_features, "WindowsNotificationClient", _FakeNotifier,
    )
    host = _FakeHost({"win_notifications_ignored": ["app.a", "", 3, "app.b"]})
    ctl = WindowsNotificationController(host)
    ctl.set_enabled(True)
    assert ctl._client.ignored == ("app.a", "app.b")   # noqa: SLF001


def test_notifications_speech_routes_to_speak_notification(monkeypatch):
    monkeypatch.setattr(
        pet_features, "WindowsNotificationClient", _FakeNotifier,
    )
    host = _FakeHost()
    ctl = WindowsNotificationController(host)
    ctl.set_enabled(True)
    ctl._client.speech_triggered.emit("You have mail")   # noqa: SLF001
    assert host.notified == ["You have mail"]


# ---------------------------------------------------------------
# Hotkeys
# ---------------------------------------------------------------


class _FakeHotkeys:
    def __init__(self, parent=None) -> None:
        self.action_triggered = _Signal()
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
    host = _FakeHost({"hotkeys": {first_action: "ctrl+alt+z"}})
    ctl = HotkeyController(host)
    assert ctl.set_enabled(True) is True
    assert ctl._client.bindings[first_action] == "ctrl+alt+z"   # noqa: SLF001
    assert host.persisted == {"hotkeys_enabled": True}


def test_hotkeys_explicit_bindings_override_settings(monkeypatch):
    monkeypatch.setattr(pet_features, "GlobalHotkeyManager", _FakeHotkeys)
    ctl = HotkeyController(_FakeHost())
    ctl.set_enabled(True, {"toggle_visible": "f8"})
    assert ctl._client.bindings == {"toggle_visible": "f8"}   # noqa: SLF001


def test_hotkeys_disable_persists_false(monkeypatch):
    monkeypatch.setattr(pet_features, "GlobalHotkeyManager", _FakeHotkeys)
    host = _FakeHost()
    ctl = HotkeyController(host)
    ctl.set_enabled(True)
    assert ctl.set_enabled(False) is True
    assert host.persisted == {"hotkeys_enabled": False}


# ---------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------


def test_build_registry_has_all_features():
    registry = build_integration_controllers(_FakeHost())
    assert set(registry) == {
        "obs", "twitch", "webhook", "windows_notifications", "hotkeys",
    }
