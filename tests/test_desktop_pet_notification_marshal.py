"""A Windows toast callback must marshal to the GUI thread with a queued signal.

``_on_notification_changed`` fires on a WinRT thread-pool thread with no Qt event
loop, so ``QTimer.singleShot`` posted there never delivered and notifications were
silently dropped. It now emits ``_notification_ready`` (a queued signal).
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.desktop_pet.windows_notification_hook import WindowsNotificationClient


def test_notification_changed_emits_the_marshal_signal(qapp):
    client = WindowsNotificationClient()
    got: list = []
    client._notification_ready.connect(got.append)
    client._on_notification_changed(
        None, SimpleNamespace(user_notification_id=42))
    assert got == [42]


def test_notification_changed_ignores_a_missing_id(qapp):
    client = WindowsNotificationClient()
    got: list = []
    client._notification_ready.connect(got.append)
    client._on_notification_changed(None, SimpleNamespace())   # no id attr
    assert got == []
