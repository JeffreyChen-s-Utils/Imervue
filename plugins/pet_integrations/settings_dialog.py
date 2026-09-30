"""The integrations' options: OBS address, Twitch channel and triggers, webhook port, ignored apps.

The text helpers are pure so the round trip between the saved settings and the
dialog's fields is testable without Qt.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

from pet_integrations.integrations import SETTING_DEFAULTS, sanitize_app_ids, sanitize_triggers

_MAX_PORT = 65535
_TRIGGER_SEPARATOR = "="


def format_triggers(triggers: object) -> str:
    """``{"hype": "Cheer"}`` → one ``keyword = Group`` line per trigger."""
    return "\n".join(f"{k} {_TRIGGER_SEPARATOR} {v}" for k, v in sanitize_triggers(triggers).items())


def parse_triggers(text: str) -> dict[str, str]:
    """``keyword = Group`` lines back into a dict; blank or malformed lines are skipped."""
    triggers: dict[str, str] = {}
    for line in text.splitlines():
        keyword, sep, group = line.partition(_TRIGGER_SEPARATOR)
        if sep and keyword.strip() and group.strip():
            triggers[keyword.strip()] = group.strip()
    return triggers


def format_app_ids(ids: object) -> str:
    """Saved app ids, one per line."""
    return "\n".join(sanitize_app_ids(ids))


def parse_app_ids(text: str) -> list[str]:
    """One app id per line; blank lines dropped, duplicates kept once in order."""
    seen: list[str] = []
    for line in text.splitlines():
        item = line.strip()
        if item and item not in seen:
            seen.append(item)
    return seen


def _tr(key: str, default: str) -> str:
    return language_wrapper.language_word_dict.get(key, default)


def _secret(value: object) -> QLineEdit:
    edit = QLineEdit(str(value))
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    return edit


def _port(value: object) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(1, _MAX_PORT)
    spin.setValue(int(value))
    return spin


class IntegrationSettingsDialog(QDialog):
    """Edit the options of the four integrations; :meth:`values` is what OK saves."""

    def __init__(self, current: dict[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_tr("pet_integrations_settings_title", "Desktop Pet Integrations"))
        merged = {**SETTING_DEFAULTS, **current}
        self._obs_host = QLineEdit(str(merged["obs_host"]))
        self._obs_port = _port(merged["obs_port"])
        self._obs_password = _secret(merged["obs_password"])
        self._twitch_channel = QLineEdit(str(merged["twitch_channel"]))
        self._twitch_oauth = _secret(merged["twitch_oauth"])
        self._twitch_triggers = QPlainTextEdit(format_triggers(merged["twitch_triggers"]))
        self._twitch_triggers.setPlaceholderText("hype = Cheer")
        self._webhook_port = _port(merged["webhook_port"])
        self._webhook_token = _secret(merged["webhook_token"])
        self._ignored = QPlainTextEdit(format_app_ids(merged["win_notifications_ignored"]))
        self._build()

    def _group(self, title_key: str, title: str, rows: list[tuple[str, str, QWidget]]) -> QGroupBox:
        box = QGroupBox(_tr(title_key, title))
        form = QFormLayout(box)
        for key, label, widget in rows:
            form.addRow(_tr(key, label), widget)
        return box

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._group("pet_integrations_obs_group", "OBS", [
            ("pet_integrations_host", "Host", self._obs_host),
            ("pet_integrations_port", "Port", self._obs_port),
            ("pet_integrations_password", "Password", self._obs_password),
        ]))
        layout.addWidget(self._group("pet_integrations_twitch_group", "Twitch chat", [
            ("pet_integrations_channel", "Channel", self._twitch_channel),
            ("pet_integrations_oauth", "OAuth token", self._twitch_oauth),
            ("pet_integrations_triggers", "Keyword = motion group", self._twitch_triggers),
        ]))
        layout.addWidget(self._group("pet_integrations_webhook_group", "Webhook", [
            ("pet_integrations_port", "Port", self._webhook_port),
            ("pet_integrations_token", "Bearer token (optional)", self._webhook_token),
        ]))
        layout.addWidget(self._group("pet_integrations_notifications_group", "Windows notifications", [
            ("pet_integrations_ignored", "Ignored app ids (one per line)", self._ignored),
        ]))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, object]:
        """The options as the pet's settings keep them."""
        return {
            "obs_host": self._obs_host.text().strip() or SETTING_DEFAULTS["obs_host"],
            "obs_port": self._obs_port.value(),
            "obs_password": self._obs_password.text(),
            "twitch_channel": self._twitch_channel.text().strip().lstrip("#"),
            "twitch_oauth": self._twitch_oauth.text().strip(),
            "twitch_triggers": parse_triggers(self._twitch_triggers.toPlainText()),
            "webhook_port": self._webhook_port.value(),
            "webhook_token": self._webhook_token.text().strip(),
            "win_notifications_ignored": parse_app_ids(self._ignored.toPlainText()),
        }
