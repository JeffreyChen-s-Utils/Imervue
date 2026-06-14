"""Concrete feature controllers for the desktop-pet overlay.

Each class here owns one "feature hook" that used to be a pair of
inline ``set_*_enabled`` / ``*_enabled`` methods on
:class:`~Imervue.desktop_pet.pet_window.PetWindow`. Extracting them
turns the window from a god-object into a thin coordinator that holds
a registry of these controllers and delegates to them — Single
Responsibility, composition over inheritance.

Every controller talks to the window only through the narrow
:class:`~Imervue.desktop_pet.pet_feature_base.FeatureHost` protocol,
so the behaviour (lazy construction, settings round-trip, signal
wiring, ``start`` / ``stop``) is preserved byte-for-byte from the
original inline implementations while becoming independently
testable.
"""
from __future__ import annotations

from Imervue.desktop_pet.obs_event_hook import ObsEventClient
from Imervue.desktop_pet.twitch_chat_hook import TwitchChatClient
from Imervue.desktop_pet.webhook_server import WebhookReceiver
from Imervue.desktop_pet.windows_notification_hook import (
    WindowsNotificationClient,
)
from Imervue.desktop_pet.hotkey_manager import (
    DEFAULT_HOTKEY_BINDINGS,
    GlobalHotkeyManager,
)
from Imervue.desktop_pet.pet_feature_base import (
    FeatureHost,
    IntegrationController,
    merge_bindings,
    sanitize_app_ids,
)

DEFAULT_OBS_HOST = "localhost"
DEFAULT_OBS_PORT = 4455
DEFAULT_WEBHOOK_PORT = 9876


class ObsHookController(IntegrationController):
    """OBS websocket event listener → motion group triggers."""

    persist_key = "obs_enabled"

    def _build_client(self) -> ObsEventClient:
        client = ObsEventClient(parent=self._host)
        client.group_triggered.connect(self._host.play_group)
        return client

    def _configure(self, client: ObsEventClient) -> None:
        client.set_endpoint(
            host=str(self._host.setting("obs_host", DEFAULT_OBS_HOST)),
            port=int(self._host.setting("obs_port", DEFAULT_OBS_PORT)),
            password=str(self._host.setting("obs_password", "")),
        )


class TwitchHookController(IntegrationController):
    """Twitch IRC chat listener → keyword-matched motion triggers."""

    persist_key = "twitch_enabled"

    def _build_client(self) -> TwitchChatClient:
        client = TwitchChatClient(parent=self._host)
        client.keyword_matched.connect(self._host.play_group)
        return client

    def _configure(self, client: TwitchChatClient) -> None:
        client.set_endpoint(
            channel=str(self._host.setting("twitch_channel", "")),
            oauth=str(self._host.setting("twitch_oauth", "")),
        )
        client.set_triggers(self._host.setting("twitch_triggers", {}) or {})


class WebhookController(IntegrationController):
    """Localhost HTTP webhook receiver → motion + speech triggers."""

    persist_key = "webhook_enabled"

    def _build_client(self) -> WebhookReceiver:
        client = WebhookReceiver(parent=self._host)
        client.command_received.connect(self._on_command)
        return client

    def _configure(self, client: WebhookReceiver) -> None:
        client.set_endpoint(
            port=int(self._host.setting("webhook_port", DEFAULT_WEBHOOK_PORT)),
            token=str(self._host.setting("webhook_token", "")),
        )

    def _on_command(self, group: str, speech: str) -> None:
        """Apply a webhook trigger. Motion + speech are independent —
        a caller might set just one."""
        if group:
            self._host.play_group(group)
        if speech and self._host.speech_on:
            self._host.speak(speech)


class WindowsNotificationController(IntegrationController):
    """Windows toast listener → motion + (optional) speech triggers."""

    persist_key = "win_notifications_enabled"

    def _build_client(self) -> WindowsNotificationClient:
        client = WindowsNotificationClient(parent=self._host)
        client.action_triggered.connect(self._host.play_group)
        client.speech_triggered.connect(self._on_speech)
        return client

    def _configure(self, client: WindowsNotificationClient) -> None:
        ignored = self._host.setting("win_notifications_ignored", []) or []
        client.set_ignored_app_ids(sanitize_app_ids(ignored))

    def _on_speech(self, line: str) -> None:
        """Route a notification's title through the speech bubble.

        We bypass the script engine because the notification text
        already carries its own content — falling back to a generic
        greeting would be wrong here.
        """
        if self._host.speech_on and line:
            self._host.speak_notification(line)   # type: ignore[attr-defined]


class HotkeyController(IntegrationController):
    """Global keyboard-hotkey listener → window actions.

    Unlike the other integration controllers, the hotkey manager is
    re-configured with the merged bindings on every enable and the
    action signal is routed back to a window-supplied handler.
    """

    persist_key = "hotkeys_enabled"

    def _build_client(self) -> GlobalHotkeyManager:
        manager = GlobalHotkeyManager(parent=self._host)
        manager.action_triggered.connect(
            self._host.on_hotkey_action,   # type: ignore[attr-defined]
        )
        return manager

    def set_enabled(  # noqa: D102 - overrides base to thread bindings
        self, enabled: bool, bindings: dict[str, str] | None = None,
    ) -> bool:
        if not enabled:
            return super().set_enabled(False)
        manager = self._ensure_client()
        effective = bindings if bindings is not None else self.persisted_bindings()
        manager.set_bindings(effective)   # type: ignore[attr-defined]
        ok = bool(manager.start())   # type: ignore[attr-defined]
        self._host.persist(hotkeys_enabled=ok)
        return ok

    def persisted_bindings(self) -> dict[str, str]:
        """Merge persisted overrides on top of the module defaults."""
        return merge_bindings(
            DEFAULT_HOTKEY_BINDINGS, self._host.setting("hotkeys", {}),
        )


def build_integration_controllers(
    host: FeatureHost,
) -> dict[str, IntegrationController]:
    """Construct the integration-controller registry for ``host``.

    Factory so the window's constructor stays a one-liner and tests
    can build the same registry against a fake host.
    """
    return {
        "obs": ObsHookController(host),
        "twitch": TwitchHookController(host),
        "webhook": WebhookController(host),
        "windows_notifications": WindowsNotificationController(host),
        "hotkeys": HotkeyController(host),
    }
