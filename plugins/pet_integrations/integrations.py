"""The desktop pet's four integrations: OBS events, Twitch chat, a local webhook, Windows toasts.

Each one is an :class:`~Imervue.desktop_pet.pet_feature_base.IntegrationController`
the plugin hands the pet with ``pet.add_integration`` (see
``ImervuePlugin.on_pet_created``). The controllers talk to the pet only through
its plugin surface — ``play_group``, ``speak``, ``speak_notification``,
``speech_on``, ``setting`` and ``persist`` — and keep their enabled flag and
their options in the pet's own settings, under the keys listed in
:data:`INTEGRATIONS` and :data:`SETTING_DEFAULTS`.
"""
from __future__ import annotations

from dataclasses import dataclass

from Imervue.desktop_pet.pet_feature_base import FeatureHost, IntegrationController

from pet_integrations.obs_event_hook import ObsEventClient
from pet_integrations.twitch_chat_hook import TwitchChatClient
from pet_integrations.webhook_server import WebhookReceiver
from pet_integrations.windows_notification_hook import WindowsNotificationClient

DEFAULT_OBS_HOST = "localhost"
DEFAULT_OBS_PORT = 4455
DEFAULT_WEBHOOK_PORT = 9876

#: Every option the integrations read from the pet's settings, with its default.
SETTING_DEFAULTS: dict[str, object] = {
    "obs_host": DEFAULT_OBS_HOST,
    "obs_port": DEFAULT_OBS_PORT,
    "obs_password": "",
    "twitch_channel": "",
    "twitch_oauth": "",
    "twitch_triggers": {},
    "webhook_port": DEFAULT_WEBHOOK_PORT,
    "webhook_token": "",
    "win_notifications_ignored": [],
}


def setting(host: FeatureHost, key: str) -> object:
    """The pet's saved value for *key*, or its default from :data:`SETTING_DEFAULTS`."""
    return host.setting(key, SETTING_DEFAULTS[key])


def sanitize_app_ids(ignored: object) -> tuple[str, ...]:
    """Coerce a saved "ignored app ids" value into a tuple of non-empty strings."""
    if not isinstance(ignored, list):
        return ()
    return tuple(item for item in ignored if isinstance(item, str) and item)


def sanitize_triggers(triggers: object) -> dict[str, str]:
    """Coerce saved Twitch triggers into ``{keyword: motion group}`` of non-empty strings."""
    if not isinstance(triggers, dict):
        return {}
    return {str(k): str(v) for k, v in triggers.items()
            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()}


class ObsHookController(IntegrationController):
    """OBS websocket event listener → motion group triggers."""

    persist_key = "obs_enabled"

    def _build_client(self) -> ObsEventClient:
        client = ObsEventClient(parent=self._host)
        client.group_triggered.connect(self._host.play_group)
        return client

    def _configure(self, client: ObsEventClient) -> None:
        client.set_endpoint(
            host=str(setting(self._host, "obs_host")),
            port=int(setting(self._host, "obs_port")),
            password=str(setting(self._host, "obs_password")),
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
            channel=str(setting(self._host, "twitch_channel")),
            oauth=str(setting(self._host, "twitch_oauth")),
        )
        client.set_triggers(sanitize_triggers(setting(self._host, "twitch_triggers")))


class WebhookController(IntegrationController):
    """Localhost HTTP webhook receiver → motion + speech triggers."""

    persist_key = "webhook_enabled"

    def _build_client(self) -> WebhookReceiver:
        client = WebhookReceiver(parent=self._host)
        client.command_received.connect(self._on_command)
        return client

    def _configure(self, client: WebhookReceiver) -> None:
        client.set_endpoint(
            port=int(setting(self._host, "webhook_port")),
            token=str(setting(self._host, "webhook_token")),
        )

    def _on_command(self, group: str, speech: str) -> None:
        """Apply a webhook trigger; the motion and the speech are independent."""
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
        client.set_ignored_app_ids(sanitize_app_ids(setting(self._host, "win_notifications_ignored")))

    def _on_speech(self, line: str) -> None:
        """Say a notification's title as it is, with the notification sound."""
        if self._host.speech_on and line:
            self._host.speak_notification(line)   # type: ignore[attr-defined]


@dataclass(frozen=True)
class Integration:
    """One integration: its key on the pet, enabled-flag setting, menu label and pip packages."""

    key: str
    persist_key: str
    label_key: str
    label: str
    controller: type[IntegrationController]
    packages: tuple[tuple[str, str], ...] = ()
    windows_only: bool = False


INTEGRATIONS: tuple[Integration, ...] = (
    Integration("obs", "obs_enabled", "pet_integrations_obs", "React to OBS events",
                ObsHookController, (("obswebsocket", "obs-websocket-py"),)),
    Integration("twitch", "twitch_enabled", "pet_integrations_twitch", "React to Twitch chat",
                TwitchHookController),
    Integration("webhook", "webhook_enabled", "pet_integrations_webhook",
                "Local webhook (127.0.0.1)", WebhookController),
    Integration("windows_notifications", "win_notifications_enabled",
                "pet_integrations_notifications", "React to Windows notifications",
                WindowsNotificationController,
                (("winrt.windows.ui.notifications.management",
                  "winrt-Windows.UI.Notifications.Management"),
                 ("winrt.windows.ui.notifications", "winrt-Windows.UI.Notifications"),
                 ("winrt.windows.foundation", "winrt-Windows.Foundation")),
                windows_only=True),
)
