"""Desktop Pet Integrations: the example of a plugin that extends the desktop pet.

The pet gets four integrations — OBS events, Twitch chat keywords, a local
webhook and Windows notifications — through the plugin API alone:

* ``on_pet_created(pet)`` hands each :class:`IntegrationController` to the pet
  (``pet.add_integration``) and turns back on the ones saved as on;
* the Plugins menu gets a *Desktop Pet Integrations* submenu with one checkable
  entry per integration, installing its optional package first when needed,
  and a *Settings…* entry for the options;
* ``on_plugin_unloaded`` takes them off the pet again (``remove_integration``),
  which stops them without forgetting that they were on.
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

from pet_integrations.integrations import INTEGRATIONS, SETTING_DEFAULTS, Integration
from pet_integrations.translations import TRANSLATIONS

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenu

logger = logging.getLogger("Imervue.plugin.pet_integrations")


def _tr(key: str, default: str) -> str:
    return language_wrapper.language_word_dict.get(key, default)


def packages_installed(integration: Integration) -> bool:
    """Whether every optional package *integration* needs can be imported."""
    for module, _pip in integration.packages:
        try:
            if importlib.util.find_spec(module) is None:
                return False
        except (ImportError, ValueError):   # a parent package missing, or a broken spec
            return False
    return True


def available_here(integration: Integration) -> bool:
    """False for a Windows-only integration on another system."""
    return not integration.windows_only or sys.platform == "win32"


class PetIntegrationsPlugin(ImervuePlugin):
    """Adds OBS, Twitch chat, webhook and Windows notification reactions to the desktop pet."""

    plugin_name = "Desktop Pet Integrations"
    plugin_version = "1.0.0"
    plugin_description = (
        "Lets the desktop pet react to OBS events, Twitch chat keywords, a local "
        "webhook and Windows notifications."
    )
    plugin_author = "Imervue"

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._pet = None
        self._actions: dict[str, QAction] = {}

    # ---- hooks ----------------------------------------------------------

    def get_translations(self) -> dict[str, dict[str, str]]:
        return TRANSLATIONS

    def on_build_menu_bar(self, plugin_menu: QMenu) -> None:
        menu = plugin_menu.addMenu(_tr("pet_integrations_menu", "Desktop Pet Integrations"))
        for integration in INTEGRATIONS:
            action = menu.addAction(_tr(integration.label_key, integration.label))
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, chosen=integration: self._on_triggered(chosen, checked))
            self._actions[integration.key] = action
        menu.addSeparator()
        settings = menu.addAction(_tr("pet_integrations_settings", "Settings…"))
        settings.triggered.connect(self.open_settings)
        self._sync_actions()

    def on_pet_created(self, pet) -> None:
        self._pet = pet
        for integration in INTEGRATIONS:
            pet.add_integration(integration.key, integration.controller(pet))
            if self._restorable(pet, integration):
                pet.integration(integration.key).set_enabled(True)
        self._sync_actions()

    def on_plugin_unloaded(self) -> None:
        if self._pet is not None:
            for integration in INTEGRATIONS:
                self._pet.remove_integration(integration.key)
        self._pet = None
        self._actions.clear()

    # ---- menu -----------------------------------------------------------

    @staticmethod
    def _restorable(pet, integration: Integration) -> bool:
        """Saved as on, and able to start here without installing anything."""
        return (bool(pet.setting(integration.persist_key, False))
                and available_here(integration) and packages_installed(integration))

    def _on_triggered(self, integration: Integration, checked: bool) -> None:
        if self._pet is None:
            self._inform(_tr("pet_integrations_no_pet",
                             "Show the desktop pet first (Desktop Pet tab), then turn this on."))
            self._sync_actions()
            return
        if not checked:
            self._pet.integration(integration.key).set_enabled(False)
            self._sync_actions()
            return
        if packages_installed(integration):
            self._enable(integration)
            return
        from Imervue.plugin.pip_installer import ensure_dependencies
        self._sync_actions()   # stays off until the install finishes
        ensure_dependencies(self.main_window, list(integration.packages),
                            lambda: self._enable(integration))

    def _enable(self, integration: Integration) -> None:
        if self._pet is None:
            return
        if not self._pet.integration(integration.key).set_enabled(True):
            self._inform(_tr(
                "pet_integrations_start_failed",
                "{name} could not start. Check its settings (Settings…) and that the "
                "service is running.").format(name=_tr(integration.label_key, integration.label)))
        self._sync_actions()

    def _sync_actions(self) -> None:
        """Each entry checked while its integration runs, enabled once the pet exists."""
        for integration in INTEGRATIONS:
            action = self._actions.get(integration.key)
            if action is None:
                continue
            controller = self._pet.integration(integration.key) if self._pet else None
            action.blockSignals(True)
            action.setChecked(bool(controller is not None and controller.is_enabled()))
            action.blockSignals(False)
            action.setEnabled(available_here(integration))

    def _inform(self, text: str) -> None:
        QMessageBox.information(self.main_window, _tr("pet_integrations_menu",
                                                      "Desktop Pet Integrations"), text)

    # ---- settings -------------------------------------------------------

    def open_settings(self) -> None:
        """Edit the integrations' options; saved ones restart the integrations that run."""
        if self._pet is None:
            self._inform(_tr("pet_integrations_no_pet",
                             "Show the desktop pet first (Desktop Pet tab), then turn this on."))
            return
        from pet_integrations.settings_dialog import IntegrationSettingsDialog
        current = {key: self._pet.setting(key, default) for key, default in SETTING_DEFAULTS.items()}
        dialog = IntegrationSettingsDialog(current, self.main_window)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.apply_settings(dialog.values())
        finally:
            dialog.deleteLater()

    def apply_settings(self, values: dict[str, object]) -> None:
        """Save *values* on the pet and restart each running integration so it reads them."""
        self._pet.persist(**values)
        for integration in INTEGRATIONS:
            controller = self._pet.integration(integration.key)
            if controller is not None and controller.is_enabled():
                controller.shutdown()
                controller.set_enabled(True)
        self._sync_actions()
