"""Tests for the Windows notification hook.

We can't drive a real ``UserNotificationListener`` from a test
(it needs an OS access prompt + an actual app firing a toast),
so this module focuses on:

* the pure :func:`notification_to_action` policy
* the ``WindowsNotificationClient.deliver`` test hook, which
  routes a synthetic notification through the signal pipeline
  exactly like the WinRT callback would
* the start() failure surface — missing winrt, non-Windows,
  denied access — all return False
"""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from Imervue.desktop_pet.windows_notification_hook import (
    ACCESS_STATUS_ALLOWED,
    ACCESS_STATUS_DENIED,
    NOTIFY_MOTION_GROUP,
    NotificationInfo,
    WindowsNotificationClient,
    notification_to_action,
)


# ---------------------------------------------------------------
# notification_to_action
# ---------------------------------------------------------------


def test_action_default_plays_notify_group_and_speaks_title():
    info = NotificationInfo(
        app_id="Microsoft.SkypeApp", title="New message", body="Hi!",
    )
    action = notification_to_action(info)
    assert action.motion_group == NOTIFY_MOTION_GROUP
    assert action.speech == "New message"


def test_action_strips_whitespace_from_title():
    info = NotificationInfo(app_id="x", title="  Reminder  ", body="")
    assert notification_to_action(info).speech == "Reminder"


def test_action_empty_title_drops_speech():
    """Body-only notifications (rare but valid) still play the
    motion but skip speech — the body is often multi-line and the
    bubble can't show much."""
    info = NotificationInfo(app_id="x", title="", body="line1\nline2")
    action = notification_to_action(info)
    assert action.motion_group == NOTIFY_MOTION_GROUP
    assert action.speech is None


def test_action_ignored_app_id_skips_everything():
    """User-configured ignore list → no motion, no speech.
    Calendar apps that fire reminders constantly are the prime
    candidate for this."""
    info = NotificationInfo(app_id="Outlook.exe", title="Stand up", body="")
    action = notification_to_action(
        info, ignored_app_ids=("Outlook.exe", "TeamsForBusiness"),
    )
    assert action.motion_group is None
    assert action.speech is None


def test_action_empty_app_id_is_not_treated_as_ignored():
    """Notifications without an app_id (system events) → still
    react. The ignore list filters by exact app_id match."""
    info = NotificationInfo(app_id="", title="Got it", body="")
    action = notification_to_action(info, ignored_app_ids=("Outlook.exe",))
    assert action.motion_group == NOTIFY_MOTION_GROUP


# ---------------------------------------------------------------
# WindowsNotificationClient — lifecycle
# ---------------------------------------------------------------


def test_client_starts_disabled(qapp):
    client = WindowsNotificationClient()
    assert client.is_running() is False


def test_client_start_on_non_windows_returns_false(qapp, monkeypatch):
    """Cross-platform safety: ``start()`` on macOS / Linux must
    not crash, just return False."""
    monkeypatch.setattr(
        "Imervue.desktop_pet.windows_notification_hook.platform.system",
        lambda: "Linux",
    )
    client = WindowsNotificationClient()
    assert client.start() is False
    assert client.is_running() is False


def test_client_start_without_winrt_returns_false(qapp, monkeypatch):
    """Missing winrt → False with no exception. Same friendly-deg
    pattern as the other optional-dep clients."""
    monkeypatch.setattr(
        "Imervue.desktop_pet.windows_notification_hook.platform.system",
        lambda: "Windows",
    )
    monkeypatch.setitem(sys.modules, "winrt", None)
    monkeypatch.setitem(
        sys.modules, "winrt.windows.ui.notifications.management", None,
    )
    client = WindowsNotificationClient()
    assert client.start() is False


def test_client_start_with_denied_access_returns_false(qapp, monkeypatch):
    """Access denied → False so the workspace can show "please
    grant permission" to the user."""
    monkeypatch.setattr(
        "Imervue.desktop_pet.windows_notification_hook.platform.system",
        lambda: "Windows",
    )

    class _DeniedListener:
        @staticmethod
        def request_access_async():
            class _Op:
                @staticmethod
                def get():
                    return ACCESS_STATUS_DENIED
            return _Op()

    client = WindowsNotificationClient()
    with patch.object(client, "_open_listener", return_value=_DeniedListener()):
        assert client.start() is False


def test_client_start_succeeds_when_access_allowed(qapp, monkeypatch):
    """Granted access + handler registration → True; subsequent
    start is idempotent."""
    monkeypatch.setattr(
        "Imervue.desktop_pet.windows_notification_hook.platform.system",
        lambda: "Windows",
    )

    class _AllowedListener:
        token_value = "fake-token"   # noqa: S105  # WinRT handler-registration token, not a credential

        @staticmethod
        def request_access_async():
            class _Op:
                @staticmethod
                def get():
                    return ACCESS_STATUS_ALLOWED
            return _Op()

        def add_notification_changed(self, _handler):
            return self.token_value

        def remove_notification_changed(self, _token):
            return None

    client = WindowsNotificationClient()
    listener_obj = _AllowedListener()
    with patch.object(client, "_open_listener", return_value=listener_obj):
        assert client.start() is True
        assert client.is_running() is True
        # Idempotent.
        assert client.start() is True
        client.stop()
        assert client.is_running() is False


def test_set_ignored_app_ids_filters_strings(qapp):
    """Non-string / empty entries get dropped — guards against
    typos in the settings file."""
    client = WindowsNotificationClient()
    client.set_ignored_app_ids(("Foo.exe", "", "Bar"))
    assert client._ignored_app_ids == ("Foo.exe", "Bar")   # noqa: SLF001


# ---------------------------------------------------------------
# deliver() — synthetic notification pipeline
# ---------------------------------------------------------------


def test_deliver_emits_all_three_signals(qapp):
    """Standard case: app not ignored → received + action + speech."""
    client = WindowsNotificationClient()
    received: list[tuple[str, str, str]] = []
    actions: list[str] = []
    speeches: list[str] = []
    client.notification_received.connect(
        lambda app, title, body: received.append((app, title, body)),
    )
    client.action_triggered.connect(actions.append)
    client.speech_triggered.connect(speeches.append)
    client.deliver(NotificationInfo(
        app_id="Slack", title="@you in #general", body="ping",
    ))
    assert received == [("Slack", "@you in #general", "ping")]
    assert actions == [NOTIFY_MOTION_GROUP]
    assert speeches == ["@you in #general"]


def test_deliver_skips_action_for_ignored_app(qapp):
    """Ignore list → notification_received still fires (so the
    user can log them), but no motion / speech."""
    client = WindowsNotificationClient()
    client.set_ignored_app_ids(("CalendarApp",))
    received: list[tuple[str, str, str]] = []
    actions: list[str] = []
    speeches: list[str] = []
    client.notification_received.connect(
        lambda app, title, body: received.append((app, title, body)),
    )
    client.action_triggered.connect(actions.append)
    client.speech_triggered.connect(speeches.append)
    client.deliver(NotificationInfo(
        app_id="CalendarApp", title="Meeting", body="",
    ))
    assert len(received) == 1
    assert actions == []
    assert speeches == []


def test_deliver_omits_speech_when_title_blank(qapp):
    client = WindowsNotificationClient()
    actions: list[str] = []
    speeches: list[str] = []
    client.action_triggered.connect(actions.append)
    client.speech_triggered.connect(speeches.append)
    client.deliver(NotificationInfo(app_id="x", title="", body="body-only"))
    assert actions == [NOTIFY_MOTION_GROUP]
    assert speeches == []


def test_stop_when_not_running_is_safe(qapp):
    client = WindowsNotificationClient()
    client.stop()
    assert client.is_running() is False


def test_shutdown_aliases_stop(qapp, monkeypatch):
    monkeypatch.setattr(
        "Imervue.desktop_pet.windows_notification_hook.platform.system",
        lambda: "Windows",
    )

    class _AllowedListener:
        @staticmethod
        def request_access_async():
            class _Op:
                @staticmethod
                def get():
                    return ACCESS_STATUS_ALLOWED
            return _Op()

        def add_notification_changed(self, _handler):
            return "tok"

        def remove_notification_changed(self, _token):
            return None

    client = WindowsNotificationClient()
    with patch.object(client, "_open_listener", return_value=_AllowedListener()):
        client.start()
    client.shutdown()
    assert client.is_running() is False


@pytest.mark.parametrize(
    "title,body,expected_speech",
    [
        ("Title only", "", "Title only"),
        ("Title", "body line", "Title"),
        ("  trim me  ", "", "trim me"),
        ("", "", None),
    ],
)
def test_action_speech_extraction(title, body, expected_speech):
    info = NotificationInfo(app_id="x", title=title, body=body)
    assert notification_to_action(info).speech == expected_speech
