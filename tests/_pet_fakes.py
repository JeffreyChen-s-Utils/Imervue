"""Fakes shared by the desktop-pet controller tests: a signal and a ``FeatureHost``."""
from __future__ import annotations


class FakeSignal:
    """Records its slots and calls them on emit, like a Qt signal."""

    def __init__(self) -> None:
        self.slots: list = []

    def connect(self, slot) -> None:
        self.slots.append(slot)

    def emit(self, *args) -> None:
        for slot in self.slots:
            slot(*args)


class FakeHost:
    """The pet surface a controller uses, recording what it is asked to do."""

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
