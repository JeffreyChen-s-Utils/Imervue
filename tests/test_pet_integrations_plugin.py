"""Tests for the Desktop Pet Integrations plugin: the example of a pet plugin.

A fake pet stands in for ``PetWindow`` (the plugin only uses its plugin
surface), and fake controllers stand in for the OBS / Twitch / webhook /
notification clients, so no socket, websocket or WinRT is touched.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QMenu, QMessageBox

from _pet_fakes import FakeHost
from pet_integrations import integrations, pet_integrations_plugin
from pet_integrations.integrations import INTEGRATIONS, SETTING_DEFAULTS
from pet_integrations.pet_integrations_plugin import (
    PetIntegrationsPlugin,
    available_here,
    packages_installed,
)
from pet_integrations.settings_dialog import (
    IntegrationSettingsDialog,
    format_app_ids,
    format_triggers,
    parse_app_ids,
    parse_triggers,
)
from pet_integrations.translations import TRANSLATIONS


class _FakeController:
    """Starts unless told to fail; remembers what the plugin asked."""

    fail = False

    def __init__(self, host) -> None:
        self.host = host
        self.running = False
        self.calls: list = []

    def set_enabled(self, enabled: bool) -> bool:
        self.calls.append(("set_enabled", enabled))
        if enabled and self.fail:
            return False
        self.running = enabled
        return True

    def is_enabled(self) -> bool:
        return self.running

    def shutdown(self) -> None:
        self.calls.append(("shutdown",))
        self.running = False


class _FakePet(FakeHost):
    """``FakeHost`` plus the integration registry of a ``PetWindow``."""

    def __init__(self, settings: dict | None = None) -> None:
        super().__init__(settings)
        self.integrations: dict = {}
        self.removed: list[str] = []

    def add_integration(self, key, controller) -> None:
        self.integrations[key] = controller

    def remove_integration(self, key) -> None:
        self.removed.append(key)
        self.integrations.pop(key, None)

    def integration(self, key):
        return self.integrations.get(key)


@pytest.fixture
def fake_controllers(monkeypatch):
    """Every integration builds a ``_FakeController`` and needs no package."""
    fakes = tuple(dataclasses.replace(i, controller=_FakeController, packages=(), windows_only=False)
                  for i in INTEGRATIONS)
    monkeypatch.setattr(pet_integrations_plugin, "INTEGRATIONS", fakes)
    _FakeController.fail = False
    return fakes


@pytest.fixture
def informed(monkeypatch):
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, text: shown.append(text))
    return shown


def _plugin():
    return PetIntegrationsPlugin(SimpleNamespace(viewer=None))


def _menu_plugin(qapp):
    plugin = _plugin()
    menu = QMenu()
    plugin.on_build_menu_bar(menu)
    return plugin, menu


def _entries(menu: QMenu):
    submenu = menu.actions()[0].menu()
    return [a for a in submenu.actions() if not a.isSeparator()]


# --- the pet hook -------------------------------------------------------------

def test_the_pet_gets_every_integration(fake_controllers):
    pet = _FakePet()
    _plugin().on_pet_created(pet)
    assert set(pet.integrations) == {"obs", "twitch", "webhook", "windows_notifications"}
    assert all(c.calls == [] for c in pet.integrations.values())   # nothing started


def test_integrations_saved_as_on_start_again(fake_controllers):
    """The flags were saved but never read back: each restart left every integration off."""
    pet = _FakePet({"obs_enabled": True, "webhook_enabled": True})
    _plugin().on_pet_created(pet)
    assert pet.integration("obs").is_enabled()
    assert pet.integration("webhook").is_enabled()
    assert not pet.integration("twitch").is_enabled()


def test_one_saved_as_on_but_missing_its_package_stays_off(fake_controllers, monkeypatch):
    monkeypatch.setattr(pet_integrations_plugin, "packages_installed", lambda i: i.key != "obs")
    pet = _FakePet({"obs_enabled": True})
    _plugin().on_pet_created(pet)
    assert pet.integration("obs").calls == []      # never asked, so its flag stays on


def test_unloading_takes_them_off_the_pet(fake_controllers):
    pet = _FakePet()
    plugin = _plugin()
    plugin.on_pet_created(pet)
    plugin.on_plugin_unloaded()
    assert sorted(pet.removed) == sorted(i.key for i in INTEGRATIONS)
    plugin.on_plugin_unloaded()                     # twice is harmless


# --- the menu -------------------------------------------------------------------

def test_the_menu_has_a_checkable_entry_per_integration_and_settings(qapp, fake_controllers):
    plugin, menu = _menu_plugin(qapp)
    entries = _entries(menu)
    assert [a.text() for a in entries] == [i.label for i in INTEGRATIONS] + ["Settings…"]
    assert all(a.isCheckable() for a in entries[:-1])
    assert not any(a.isChecked() for a in entries)
    plugin.on_plugin_unloaded()


def test_turning_one_on_before_the_pet_exists_explains(qapp, fake_controllers, informed):
    plugin, menu = _menu_plugin(qapp)
    obs = _entries(menu)[0]
    obs.trigger()
    assert informed and "desktop pet" in informed[0]
    assert not obs.isChecked()


def test_turning_one_on_starts_it_and_checks_the_entry(qapp, fake_controllers):
    plugin, menu = _menu_plugin(qapp)
    pet = _FakePet()
    plugin.on_pet_created(pet)
    twitch = _entries(menu)[1]
    twitch.trigger()
    assert pet.integration("twitch").is_enabled()
    assert twitch.isChecked()
    twitch.trigger()                                  # and off again
    assert not pet.integration("twitch").is_enabled()
    assert not twitch.isChecked()


def test_a_start_that_fails_says_so_and_stays_unchecked(qapp, fake_controllers, informed):
    plugin, menu = _menu_plugin(qapp)
    plugin.on_pet_created(_FakePet())
    _FakeController.fail = True
    webhook = _entries(menu)[2]
    webhook.trigger()
    assert not webhook.isChecked()
    assert "could not start" in informed[0]


def test_a_missing_package_is_installed_first(qapp, fake_controllers, monkeypatch):
    from Imervue.plugin import pip_installer
    asked: list = []
    monkeypatch.setattr(pet_integrations_plugin, "packages_installed", lambda _i: False)
    monkeypatch.setattr(pip_installer, "ensure_dependencies",
                        lambda parent, packages, on_ready: asked.append((packages, on_ready)))
    plugin, menu = _menu_plugin(qapp)
    pet = _FakePet()
    plugin.on_pet_created(pet)
    obs = _entries(menu)[0]
    obs.trigger()
    assert len(asked) == 1
    assert not pet.integration("obs").is_enabled()     # waits for the install
    asked[0][1]()                                        # installed
    assert pet.integration("obs").is_enabled()
    assert obs.isChecked()


def test_a_windows_only_entry_is_disabled_elsewhere(qapp, fake_controllers, monkeypatch):
    windows_only = dataclasses.replace(fake_controllers[3], windows_only=True)
    monkeypatch.setattr(pet_integrations_plugin, "INTEGRATIONS", (*fake_controllers[:3], windows_only))
    monkeypatch.setattr(pet_integrations_plugin.sys, "platform", "linux")
    plugin, menu = _menu_plugin(qapp)
    assert not _entries(menu)[3].isEnabled()
    assert _entries(menu)[0].isEnabled()


# --- settings ---------------------------------------------------------------------

def test_apply_settings_saves_and_restarts_the_running_ones(fake_controllers):
    plugin = _plugin()
    pet = _FakePet()
    plugin.on_pet_created(pet)
    pet.integration("webhook").set_enabled(True)
    plugin.apply_settings({"webhook_port": 9000})
    assert pet.persisted["webhook_port"] == 9000
    assert pet.integration("webhook").calls[-2:] == [("shutdown",), ("set_enabled", True)]
    assert pet.integration("obs").calls == []


def test_settings_without_a_pet_explain(qapp, fake_controllers, informed):
    _plugin().open_settings()
    assert informed


def test_open_settings_saves_what_the_dialog_returns(qapp, fake_controllers, monkeypatch):
    from PySide6.QtWidgets import QDialog
    plugin = _plugin()
    plugin.main_window = None        # the dialog's parent; a transient widget would crash teardown
    pet = _FakePet({"obs_port": 4444})
    plugin.on_pet_created(pet)
    seen: dict = {}

    def accept(dialog):
        seen.update(dialog.values())
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(IntegrationSettingsDialog, "exec", accept)
    plugin.open_settings()
    assert seen["obs_port"] == 4444
    assert pet.persisted["obs_port"] == 4444


def test_the_dialog_round_trips_every_option(qapp):
    current = {"obs_host": "studio", "obs_port": 4460, "obs_password": "pw",
               "twitch_channel": "#me", "twitch_oauth": " oauth:x ",
               "twitch_triggers": {"hype": "Cheer"}, "webhook_port": 9999,
               "webhook_token": "t", "win_notifications_ignored": ["a.b", "c.d"]}
    dialog = IntegrationSettingsDialog(current, None)
    try:
        values = dialog.values()
    finally:
        dialog.deleteLater()
    assert values == {**current, "twitch_channel": "me", "twitch_oauth": "oauth:x"}


def test_the_dialog_fills_in_defaults(qapp):
    dialog = IntegrationSettingsDialog({}, None)
    try:
        values = dialog.values()
    finally:
        dialog.deleteLater()
    assert values == SETTING_DEFAULTS


def test_the_trigger_box_explains_the_keyword_syntax(qapp):
    dialog = IntegrationSettingsDialog({}, None)
    try:
        tip = dialog._twitch_triggers.toolTip()               # noqa: SLF001
    finally:
        dialog.deleteLater()
    assert all(form in tip for form in ("=hi", "!dance*", "/go+al/"))


@pytest.mark.parametrize(("text", "triggers"), [
    ("hype = Cheer\nhello=Wave", {"hype": "Cheer", "hello": "Wave"}),
    ("no separator\n = Empty\nkey =\n\n", {}),
    ("a = b = c", {"a": "b = c"}),
    ("=hi = Wave\n=hey=Bow", {"=hi": "Wave", "=hey": "Bow"}),
    ("/a=b+/ = Cheer\n!dance* = Dance", {"/a=b+/": "Cheer", "!dance*": "Dance"}),
    ("= = Empty\n/x/ =", {}),
])
def test_parse_triggers(text, triggers):
    assert parse_triggers(text) == triggers


def test_trigger_and_app_id_text_round_trip():
    assert parse_triggers(format_triggers({"hype": "Cheer", "": "x", "k": 3})) == {"hype": "Cheer"}
    special = {"=hi": "Wave", "/go+al/": "Cheer", "!dance*": "Dance"}
    assert parse_triggers(format_triggers(special)) == special
    assert parse_app_ids(format_app_ids(["a", "", 3, "b"])) == ["a", "b"]
    assert parse_app_ids(" a \n\na\nb") == ["a", "b"]


# --- helpers and packaging --------------------------------------------------------

def test_packages_installed_checks_every_module(monkeypatch):
    obs = INTEGRATIONS[0]
    found = {"obswebsocket"}
    monkeypatch.setattr(pet_integrations_plugin.importlib.util, "find_spec",
                        lambda name: object() if name in found else None)
    assert packages_installed(obs)
    found.clear()
    assert not packages_installed(obs)
    assert packages_installed(INTEGRATIONS[1])        # Twitch needs nothing


def test_a_broken_parent_package_counts_as_missing(monkeypatch):
    def broken(_name):
        raise ModuleNotFoundError("winrt")

    monkeypatch.setattr(pet_integrations_plugin.importlib.util, "find_spec", broken)
    assert not packages_installed(INTEGRATIONS[3])


def test_available_here(monkeypatch):
    notifications = INTEGRATIONS[3]
    monkeypatch.setattr(pet_integrations_plugin.sys, "platform", "darwin")
    assert not available_here(notifications)
    assert available_here(INTEGRATIONS[0])
    monkeypatch.setattr(pet_integrations_plugin.sys, "platform", "win32")
    assert available_here(notifications)


def test_the_integrations_are_the_four_with_their_keys():
    assert [(i.key, i.persist_key) for i in INTEGRATIONS] == [
        ("obs", "obs_enabled"), ("twitch", "twitch_enabled"), ("webhook", "webhook_enabled"),
        ("windows_notifications", "win_notifications_enabled")]
    assert all(i.controller.persist_key == i.persist_key for i in INTEGRATIONS)


def test_every_language_has_every_string():
    english = set(TRANSLATIONS["English"])
    assert set(TRANSLATIONS) == {"English", "Traditional_Chinese", "Chinese", "Japanese", "Korean"}
    for words in TRANSLATIONS.values():
        assert set(words) == english
        assert all(value.strip() for value in words.values())


def test_the_package_exposes_the_plugin_class():
    import pet_integrations
    assert pet_integrations.plugin_class is PetIntegrationsPlugin


def test_twitch_triggers_are_cleaned_before_use():
    assert integrations.sanitize_triggers({"hi": "Wave", "": "x", "k": 3, 5: "y"}) == {"hi": "Wave"}
    assert integrations.sanitize_triggers(["not", "a", "dict"]) == {}
