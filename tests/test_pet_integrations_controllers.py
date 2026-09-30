"""Unit tests for the Desktop Pet Integrations plugin's controllers.

Each controller is built against a fake host + a monkeypatched fake
client so the configure / signal-routing logic is verified without a
real websocket / socket / WinRT dependency or any Qt widget.
"""
from __future__ import annotations

from _pet_fakes import FakeHost, FakeSignal
from pet_integrations import integrations
from pet_integrations.integrations import (
    ObsHookController,
    TwitchHookController,
    WebhookController,
    WindowsNotificationController,
    sanitize_app_ids,
)


# ---------------------------------------------------------------
# OBS
# ---------------------------------------------------------------


class _FakeObs:
    def __init__(self, parent=None) -> None:
        self.group_triggered = FakeSignal()
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
    monkeypatch.setattr(integrations, "ObsEventClient", _FakeObs)
    host = FakeHost({"obs_host": "h", "obs_port": 9, "obs_password": "p"})
    ctl = ObsHookController(host)
    ctl.set_enabled(True)
    assert ctl._client.endpoint == {"host": "h", "port": 9, "password": "p"}   # noqa: SLF001
    assert host.persisted == {"obs_enabled": True}


def test_obs_group_signal_routes_to_play(monkeypatch):
    monkeypatch.setattr(integrations, "ObsEventClient", _FakeObs)
    host = FakeHost()
    ctl = ObsHookController(host)
    ctl.set_enabled(True)
    ctl._client.group_triggered.emit("Wave")   # noqa: SLF001
    assert host.played == ["Wave"]


# ---------------------------------------------------------------
# Twitch
# ---------------------------------------------------------------


class _FakeTwitch:
    def __init__(self, parent=None) -> None:
        self.keyword_matched = FakeSignal()
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
    monkeypatch.setattr(integrations, "TwitchChatClient", _FakeTwitch)
    host = FakeHost({
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
        self.command_received = FakeSignal()
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
    monkeypatch.setattr(integrations, "WebhookReceiver", _FakeWebhook)
    host = FakeHost()
    ctl = WebhookController(host)
    ctl.set_enabled(True)
    ctl._client.command_received.emit("Dance", "hello")   # noqa: SLF001
    assert host.played == ["Dance"]
    assert host.spoken == ["hello"]


def test_webhook_command_speech_suppressed_when_speech_off(monkeypatch):
    monkeypatch.setattr(integrations, "WebhookReceiver", _FakeWebhook)
    host = FakeHost()
    host.speech_on = False
    ctl = WebhookController(host)
    ctl.set_enabled(True)
    ctl._client.command_received.emit("Dance", "hello")   # noqa: SLF001
    assert host.played == ["Dance"]
    assert host.spoken == []


def test_webhook_command_motion_only(monkeypatch):
    monkeypatch.setattr(integrations, "WebhookReceiver", _FakeWebhook)
    host = FakeHost()
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
        self.action_triggered = FakeSignal()
        self.speech_triggered = FakeSignal()
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
        integrations, "WindowsNotificationClient", _FakeNotifier,
    )
    host = FakeHost({"win_notifications_ignored": ["app.a", "", 3, "app.b"]})
    ctl = WindowsNotificationController(host)
    ctl.set_enabled(True)
    assert ctl._client.ignored == ("app.a", "app.b")   # noqa: SLF001


def test_notifications_speech_routes_to_speak_notification(monkeypatch):
    monkeypatch.setattr(
        integrations, "WindowsNotificationClient", _FakeNotifier,
    )
    host = FakeHost()
    ctl = WindowsNotificationController(host)
    ctl.set_enabled(True)
    ctl._client.speech_triggered.emit("You have mail")   # noqa: SLF001
    assert host.notified == ["You have mail"]


# ---------------------------------------------------------------
# sanitize_app_ids
# ---------------------------------------------------------------


def test_sanitize_app_ids_keeps_only_nonempty_strings():
    assert sanitize_app_ids(["a", "", "b", 3, None, "c"]) == ("a", "b", "c")


def test_sanitize_app_ids_rejects_non_list():
    assert sanitize_app_ids("a,b,c") == ()
    assert sanitize_app_ids(None) == ()
    assert sanitize_app_ids({"a": 1}) == ()


def test_sanitize_app_ids_empty_list():
    assert sanitize_app_ids([]) == ()
