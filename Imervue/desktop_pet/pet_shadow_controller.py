"""Drop-shadow controller for the desktop-pet overlay.

Centralises the three shadow knobs (enabled / opacity / scale) that
:class:`~Imervue.desktop_pet.pet_window.PetWindow` used to manage with
four near-identical inline methods, each re-reading two of the three
settings to call ``canvas.set_pet_shadow(...)``. Folding that into one
controller removes the duplicated apply-block and keeps the clamp ranges
in one place.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from Imervue.puppet.canvas import PuppetCanvas

DEFAULT_OPACITY = 0.7
DEFAULT_SCALE = 1.0
MAX_OPACITY = 1.0
MAX_SCALE = 2.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class PetShadowController:
    """Applies + persists the pet's drop-shadow settings.

    ``read_setting`` fetches a persisted value with a default;
    ``persist`` writes a settings field. Splitting these out keeps the
    controller decoupled from the window's settings dict shape.
    """

    def __init__(
        self,
        canvas: PuppetCanvas,
        read_setting: Callable[[str, object], object],
        persist: Callable[..., None],
    ) -> None:
        self._canvas = canvas
        self._read = read_setting
        self._persist = persist

    def _opacity(self) -> float:
        return float(self._read("pet_shadow_opacity", DEFAULT_OPACITY))

    def _scale(self) -> float:
        return float(self._read("pet_shadow_scale", DEFAULT_SCALE))

    def apply_initial(self) -> None:
        """Push the persisted shadow state onto the canvas so the very
        first paint already includes it."""
        self._canvas.set_pet_shadow(
            enabled=bool(self._read("pet_shadow_enabled", True)),
            opacity=self._opacity(),
            scale=self._scale(),
        )

    def is_enabled(self) -> bool:
        return bool(self._canvas.pet_shadow_enabled())

    def set_enabled(self, enabled: bool) -> None:
        self._persist(pet_shadow_enabled=bool(enabled))
        self._canvas.set_pet_shadow(
            enabled=bool(enabled), opacity=self._opacity(), scale=self._scale(),
        )

    def set_opacity(self, value: float) -> None:
        clamped = _clamp(float(value), 0.0, MAX_OPACITY)
        self._persist(pet_shadow_opacity=clamped)
        self._canvas.set_pet_shadow(
            enabled=self.is_enabled(), opacity=clamped, scale=self._scale(),
        )

    def set_scale(self, value: float) -> None:
        clamped = _clamp(float(value), 0.0, MAX_SCALE)
        self._persist(pet_shadow_scale=clamped)
        self._canvas.set_pet_shadow(
            enabled=self.is_enabled(), opacity=self._opacity(), scale=clamped,
        )
