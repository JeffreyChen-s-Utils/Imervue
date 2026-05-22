"""Registry of live :class:`PetWindow` instances.

Until this module existed every consumer (workspace, tray) assumed
a single pet. The registry centralises lifecycle for any number of
pets keyed by stable pet id:

* :meth:`spawn` — create + show the window for a pet id (or return
  the existing window when already spawned).
* :meth:`despawn` — hide + delete the window. Settings persist;
  the next :meth:`spawn` re-reads them.
* :meth:`primary` — the default pet's window (always there once
  the workspace asks for it).
* :meth:`pet_ids` — every spawned pet id, primary first.

The registry doesn't *create* settings slots — :mod:`pet_settings`
already does that on first read. It just owns the live Qt objects
and keeps the workspace + tray talking to the right ``PetWindow``.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_window import PetWindow

if TYPE_CHECKING:
    pass

logger = logging.getLogger("Imervue.desktop_pet.pet_registry")


class PetRegistry(QObject):
    """Owns every live :class:`PetWindow` instance.

    Constructed once per application (the workspace owns one). All
    pet creation / destruction goes through here so external callers
    (tray, hotkeys, scripted spawn) don't end up with parallel pet
    objects pointing at the same settings slot.
    """

    pet_spawned = Signal(str)
    """Emitted with a pet id each time :meth:`spawn` actually
    creates a new window (no-op spawns don't re-emit)."""

    pet_despawned = Signal(str)
    """Emitted with a pet id each time :meth:`despawn` actually
    deletes a window."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pets: dict[str, PetWindow] = {}

    # ---- lifecycle -------------------------------------------------

    def spawn(self, pet_id: str = pet_settings.DEFAULT_PET_ID) -> PetWindow:
        """Return the window for ``pet_id``, creating it on first
        ask. Newly-created windows are not shown — the caller wires
        the visibility toggle (workspace checkbox, hotkey)."""
        if not pet_id:
            raise ValueError("pet_id must be a non-empty string")
        existing = self._pets.get(pet_id)
        if existing is not None:
            return existing
        # Non-default pets must have a settings slot before spawn so
        # subsequent ``pet_settings.update(pet_id, ...)`` calls land
        # somewhere. The default pet is handled implicitly by
        # ``load(DEFAULT_PET_ID)``.
        if pet_id != pet_settings.DEFAULT_PET_ID:
            pet_settings.add_pet(pet_id)
        window = PetWindow(pet_id=pet_id)
        self._pets[pet_id] = window
        self.pet_spawned.emit(pet_id)
        return window

    def despawn(self, pet_id: str) -> bool:
        """Hide + destroy the window for ``pet_id``. Settings are
        *not* removed — the same id can be respawned later. The
        primary pet (:data:`pet_settings.DEFAULT_PET_ID`) can be
        despawned too (the workspace's hide flow may want this);
        the registry doesn't enforce "always alive"."""
        window = self._pets.pop(pet_id, None)
        if window is None:
            return False
        try:
            window.hide()
        finally:
            window.deleteLater()
        self.pet_despawned.emit(pet_id)
        return True

    def despawn_all(self) -> None:
        """Tear down every live pet — used by the workspace's
        teardown so test runs don't leak Qt windows between cases."""
        for pet_id in list(self._pets.keys()):
            self.despawn(pet_id)

    # ---- inspection ------------------------------------------------

    def get(self, pet_id: str) -> PetWindow | None:
        return self._pets.get(pet_id)

    def primary(self) -> PetWindow:
        """Return the default pet's window, spawning it if needed.
        Callers (workspace, tray) that don't care about multi-pet
        use this and stay single-pet-shaped."""
        return self.spawn(pet_settings.DEFAULT_PET_ID)

    def pet_ids(self) -> list[str]:
        """Currently-spawned pets, primary first when present then
        insertion order. Independent of what :mod:`pet_settings`
        has persisted — the registry only reports what's live."""
        ids = list(self._pets.keys())
        if pet_settings.DEFAULT_PET_ID in ids:
            ids.remove(pet_settings.DEFAULT_PET_ID)
            ids.insert(0, pet_settings.DEFAULT_PET_ID)
        return ids

    def __len__(self) -> int:
        return len(self._pets)

    def __iter__(self):
        return iter(self._pets.values())

    def __contains__(self, pet_id: object) -> bool:
        return pet_id in self._pets
