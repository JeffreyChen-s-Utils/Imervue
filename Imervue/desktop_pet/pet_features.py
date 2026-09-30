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
testable. The OBS, Twitch chat, webhook and Windows-notification
integrations are the Desktop Pet Integrations plugin
(``plugins/pet_integrations``); they join this registry through
``PetWindow.add_integration``.
"""
from __future__ import annotations

from Imervue.desktop_pet.hotkey_manager import (
    DEFAULT_HOTKEY_BINDINGS,
    GlobalHotkeyManager,
)
from Imervue.desktop_pet.pet_feature_base import (
    FeatureHost,
    IntegrationController,
    merge_bindings,
)


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
    return {"hotkeys": HotkeyController(host)}
