"""Windows toast notification → desktop-pet motion / speech hook.

When another app fires a Windows toast (Outlook reminder, Discord
DM, Slack mention, OBS recording start, etc.), the pet plays a
``Notify`` motion group and optionally speaks the notification's
title — same group-name convention the OBS / Twitch / drag-drop
hooks use.

The Windows API in question is ``UserNotificationListener``
(``Windows.UI.Notifications.Management``). It requires user
permission — the first time we connect, Windows shows a system
dialog asking the user to grant access. The :class:`winrt`
packages ship as platform wheels (no compile step needed) but
remain optional: missing import or denied permission falls back
to a workspace status message rather than crashing the pet.

Non-Windows OSes get a stub that always reports "not supported".
The pet still works fine without notification reactions; the
feature toggle simply stays off.

Pure helper :func:`notification_to_action` decides what to do
with each notification — kept Qt-free / WinRT-free so the
filtering policy (allow-list, ignore-list) is testable without
the optional dep.
"""
from __future__ import annotations

import logging
import platform
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    pass

logger = logging.getLogger("Imervue.desktop_pet.windows_notification_hook")

NOTIFY_MOTION_GROUP: str = "Notify"
"""Group name the pet plays on every notification by default. Rigs
without it silently no-op — same opt-in-via-authoring convention
as the other event hooks."""

ACCESS_STATUS_ALLOWED: int = 1
ACCESS_STATUS_DENIED: int = 2
"""Mirror of Windows.UI.Notifications.Management
``UserNotificationListenerAccessStatus`` so tests don't need to
import winrt to assert on access-status branches."""


@dataclass(frozen=True)
class NotificationInfo:
    """Pure record of one toast notification's payload. Used as the
    input to :func:`notification_to_action`; mirrors what we can
    pull out of ``UserNotification`` without any WinRT runtime
    types leaking into the test surface."""

    app_id: str
    title: str
    body: str


@dataclass(frozen=True)
class NotificationAction:
    """What the pet should do in response. ``motion_group`` is the
    Cubism group name to play (``None`` skips motion); ``speech``
    is what to drop into the speech bubble (``None`` skips speech).
    Returning everything-None means "ignore this notification"."""

    motion_group: str | None
    speech: str | None


def notification_to_action(
    info: NotificationInfo,
    *,
    ignored_app_ids: tuple[str, ...] = (),
) -> NotificationAction:
    """Map a notification to the pet's response.

    Default policy:

    * App in ``ignored_app_ids`` → no reaction (cuts spammy
      always-on apps like calendar reminders for the user).
    * Otherwise → play :data:`NOTIFY_MOTION_GROUP` + speak the
      notification title (the body is often multi-line / too long
      for the speech bubble).
    """
    if info.app_id and info.app_id in ignored_app_ids:
        return NotificationAction(motion_group=None, speech=None)
    speech = info.title.strip() if info.title else None
    return NotificationAction(motion_group=NOTIFY_MOTION_GROUP, speech=speech or None)


class WindowsNotificationClient(QObject):
    """QObject wrapping ``UserNotificationListener``.

    Two-stage lifecycle:

    1. :meth:`start` requests Windows access permission. The OS
       shows a one-time dialog; subsequent starts return cached
       status. Returns ``False`` if access is denied / undecided
       so the workspace can surface "permission required".
    2. After access is granted, we register an event handler.
       Windows fires the handler from its own thread; we re-emit
       through :attr:`notification_received` (thread-safe) and
       process it on the GUI thread.
    """

    notification_received = Signal(str, str, str)
    """Emitted with ``(app_id, title, body)`` on every notification."""

    action_triggered = Signal(str)
    """Emitted with the motion-group name after applying the
    policy filter. PetWindow connects this to
    :meth:`PetWindow.play_random_motion_in_group`."""

    speech_triggered = Signal(str)
    """Emitted with the speech-bubble line per
    :func:`notification_to_action`. ``PetWindow`` is the consumer."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._listener = None
        self._handler_token = None
        self._ignored_app_ids: tuple[str, ...] = ()

    # ---- public API -----------------------------------------------

    def is_running(self) -> bool:
        return self._listener is not None and self._handler_token is not None

    def set_ignored_app_ids(self, ids: tuple[str, ...]) -> None:
        """Replace the ignore-list. Effective on the next
        notification arrival; the listener stays running."""
        self._ignored_app_ids = tuple(str(i) for i in ids if i)

    def start(self) -> bool:
        """Open the listener + register the handler. Returns
        ``True`` only on a complete success path; ``False`` on any
        of: non-Windows OS, missing winrt, access denied, handler
        registration error."""
        if self.is_running():
            return True
        if platform.system() != "Windows":
            logger.info("windows notifications: not on Windows; skipping")
            return False
        listener = self._open_listener()
        if listener is None:
            return False
        if not self._check_access(listener):
            return False
        try:
            self._handler_token = listener.add_notification_changed(
                self._on_notification_changed,
            )
        except Exception as exc:   # noqa: BLE001 - winrt errors vary by Windows build
            logger.warning("notification handler register failed: %s", exc)
            return False
        self._listener = listener
        return True

    def stop(self) -> None:
        """Unregister the handler + drop the listener reference."""
        listener = self._listener
        token = self._handler_token
        self._listener = None
        self._handler_token = None
        if listener is None or token is None:
            return
        try:
            listener.remove_notification_changed(token)
        except Exception as exc:   # noqa: BLE001 - winrt teardown errors vary
            logger.warning("notification handler unregister failed: %s", exc)

    def shutdown(self) -> None:
        self.stop()

    def deliver(self, info: NotificationInfo) -> None:
        """Public test hook: route ``info`` through the policy +
        signal pipeline as if WinRT had fired it. Lets tests verify
        the dispatch wiring without involving the OS listener."""
        self.notification_received.emit(info.app_id, info.title, info.body)
        action = notification_to_action(
            info, ignored_app_ids=self._ignored_app_ids,
        )
        if action.motion_group:
            self.action_triggered.emit(action.motion_group)
        if action.speech:
            self.speech_triggered.emit(action.speech)

    # ---- internal -------------------------------------------------

    def _open_listener(self):
        try:
            from winrt.windows.ui.notifications.management import (
                UserNotificationListener,
            )
        except ImportError:
            logger.info(
                "winrt-Windows.UI.Notifications.Management not installed; "
                "Windows notification hook unavailable",
            )
            return None
        try:
            return UserNotificationListener.current
        except Exception as exc:   # noqa: BLE001 - winrt static access varies
            logger.warning("UserNotificationListener.current failed: %s", exc)
            return None

    def _check_access(self, listener) -> bool:
        """Block briefly on the access-request awaitable. ``get``
        is the supported sync escape hatch; we cap it via WinRT's
        own IAsyncOperation timeout semantics (a few seconds at
        worst, since the prompt is user-driven and access is
        cached after the first call)."""
        try:
            status = listener.request_access_async().get()
        except Exception as exc:   # noqa: BLE001 - winrt async surface
            logger.warning("notification access request failed: %s", exc)
            return False
        # ALLOWED == 1; anything else (DENIED, UNSPECIFIED) → no.
        if int(status) != ACCESS_STATUS_ALLOWED:
            logger.info("notification access denied (status=%s)", status)
            return False
        return True

    def _on_notification_changed(self, sender, args) -> None:   # noqa: ARG002
        """Fired by Windows from a background thread when a toast
        arrives. We marshal back to the GUI thread via
        ``QTimer.singleShot`` — Qt signals are emit-safe from any
        thread, but the *delivery* needs the GUI loop, and we want
        the WinRT lookups (`listener.get_notification`) to happen
        on the GUI thread for consistency with the rest of the
        client."""
        notification_id = getattr(args, "user_notification_id", None)
        if notification_id is None:
            return
        QTimer.singleShot(
            0,
            lambda nid=notification_id: self._fetch_and_dispatch(nid),
        )

    def _fetch_and_dispatch(self, notification_id: int) -> None:
        """GUI-thread tail of the WinRT callback: pull the
        notification payload, run the policy, fire signals. Any
        failure is logged and dropped — a malformed payload mustn't
        kill the listener."""
        listener = self._listener
        if listener is None:
            return
        try:
            user_notification = listener.get_notification(notification_id)
        except Exception as exc:   # noqa: BLE001 - winrt lookup errors vary
            logger.warning("notification fetch failed: %s", exc)
            return
        if user_notification is None:
            return
        info = _extract_info(user_notification)
        if info is None:
            return
        self.deliver(info)


def _extract_info(user_notification) -> NotificationInfo | None:
    """Pull ``(app_id, title, body)`` out of a WinRT
    ``UserNotification``. Tolerant of missing fields — apps push
    notifications with all kinds of malformed payloads."""
    try:
        app_id = str(user_notification.app_info.app_user_model_id or "")
    except Exception:   # noqa: BLE001 - some apps don't expose app_info
        app_id = ""
    title = ""
    body = ""
    try:
        toast = user_notification.notification.visual.get_binding("ToastGeneric")
        if toast is not None:
            text_elements = list(toast.get_text_elements())
            if text_elements:
                title = str(text_elements[0].text or "")
            if len(text_elements) > 1:
                body = " ".join(
                    str(elem.text or "") for elem in text_elements[1:]
                ).strip()
    except Exception as exc:   # noqa: BLE001 - WinRT visual structure varies
        logger.debug("notification extract failed: %s", exc)
    if not (title or body):
        return None
    return NotificationInfo(app_id=app_id, title=title, body=body)
