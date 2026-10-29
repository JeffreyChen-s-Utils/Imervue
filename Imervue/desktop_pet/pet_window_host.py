"""Settings, integrations, menu rows and sizing for :class:`PetWindow`.

``PetHostMixin`` is the persistence seam (every saved setting goes through
``_persist`` so it lands in this pet's slot and emits ``setting_changed``), the
``FeatureHost`` adapter the integration controllers call, the plugin
integration registry, the context-menu row builders, the size presets, and the
startup restore of position and persisted drivers. It relies on the host
window's ``_pet_id``, ``_settings``, ``_features``, ``_canvas_drivers`` and
flag attributes plus the toggle setters mixed in from the sibling modules.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from Imervue.desktop_pet import pet_placement
from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_context_menu import build_context_menu
from Imervue.system.best_effort import best_effort

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint

    from Imervue.desktop_pet.pet_feature_base import IntegrationController

SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "small": (200, 300),
    "medium": (320, 480),
    "large": (480, 720),
}

PET_IDLE_CYCLE_DURATION_S: float = 4.0
"""Override the puppet module's 8s default for the desktop overlay.
On the desktop the pet is decorative and benefits from livelier
turnover; the editor workspace still uses the slower default so
authoring previews aren't constantly interrupted."""


class PetHostMixin:
    """Persistence, integration, menu-row and sizing behaviour mixed into ``PetWindow``."""

    def _apply_edge_snap(self) -> None:   # pragma: no cover - Qt geometry
        pet_placement.apply_edge_snap(self)

    # =====================================================================
    # Context menu
    # =====================================================================

    def _show_context_menu(self, global_pos: QPoint) -> None:   # pragma: no cover - Qt UI
        build_context_menu(self, global_pos)

    def driver_menu_entries(
        self,
    ) -> list[tuple[str, str, bool, Any]]:   # pragma: no cover - Qt UI
        """Rows for the "Live drivers" submenu: ``(label_key,
        default_label, currently_running, setter)``. Each running
        flag is sourced from the driver's own object so the menu
        check-state always matches the world."""
        drivers = self._canvas_drivers
        return [
            ("desktop_pet_auto_idle", "Auto idle (breath + drift)",
             drivers.idle_running(), self.set_auto_idle_enabled),
            ("desktop_pet_idle_motion", "Idle motions",
             drivers.idle_motion_running(), self.set_idle_motion_enabled),
            ("desktop_pet_auto_blink", "Auto-blink",
             self._input_engine.blink_enabled(), self.set_auto_blink_enabled),
            ("desktop_pet_drag_track", "Drag-track head",
             self._input_engine.drag_enabled(), self.set_drag_track_enabled),
            ("desktop_pet_mouse_gaze", "Mouse gaze (eyes follow cursor)",
             drivers.gaze_running(), self.set_mouse_gaze_enabled),
            ("desktop_pet_mic_lipsync", "Mic lip-sync",
             self._input_engine.lipsync_enabled(), self.set_mic_lipsync_enabled),
            ("desktop_pet_webcam", "Webcam tracking",
             drivers.webcam_running(), self.set_webcam_tracking_enabled),
        ]

    def toggle_menu_entries(
        self,
    ) -> list[tuple[str, str, bool, Any]]:   # pragma: no cover - Qt UI
        """Rows for the five top-level checkable toggles: ``(label_key,
        default_label, current_state, setter)``."""
        return [
            ("desktop_pet_anchor", "Lock position",
             self._anchor_locked, self.set_anchor_locked),
            ("desktop_pet_click_through", "Click-through (let mouse pass)",
             self._click_through, self.set_click_through),
            ("desktop_pet_on_bottom", "Always on bottom (desktop widget)",
             self._always_on_bottom, self.set_always_on_bottom),
            ("desktop_pet_hide_fullscreen", "Hide when other app is fullscreen",
             self._hide_on_fullscreen, self.set_hide_on_fullscreen),
            ("desktop_pet_speech", "Speech bubble on click",
             self._speech_enabled, self.set_speech_enabled),
        ]

    def current_size_preset(self) -> str:   # pragma: no cover - Qt UI
        """Public alias of the active size-preset name for the menu."""
        return self._current_size_preset()

    # =====================================================================
    # Live drivers
    # =====================================================================

    def set_idle_motion_enabled(self, enabled: bool) -> None:
        self._canvas_drivers.set_idle_motion_enabled(
            bool(enabled), PET_IDLE_CYCLE_DURATION_S,
        )
        self._persist_driver("idle_motion", bool(enabled))

    def _persist_driver(self, key: str, value: bool) -> None:
        drivers = dict(self._settings.get("drivers", {}))
        drivers[key] = bool(value)
        self._settings["drivers"] = drivers
        self._persist(drivers=drivers)

    def _persist(self, **fields: Any) -> None:
        """Thread the pet's own id through :func:`pet_settings.update`
        so each instance writes to its own slot. Single seam for the
        whole window — every persist call goes through here, which
        keeps the multi-pet refactor from sprawling across 20+ call
        sites."""
        pet_settings.update(self._pet_id, **fields)
        for key, value in fields.items():
            self.setting_changed.emit(key, value)

    # ---- FeatureHost adapter ------------------------------------
    # The thin surface the integration controllers depend on (see
    # pet_feature_base.FeatureHost). Each call forwards to the
    # window's existing machinery so controller behaviour stays
    # identical to the old inline implementations.

    def persist(self, **fields: Any) -> None:
        self._persist(**fields)

    def setting(self, key: str, default: Any) -> Any:
        return self._settings.get(key, default)

    def persist_driver(self, key: str, value: bool) -> None:
        self._persist_driver(key, value)

    def on_hotkey_action(self, action: str) -> None:
        self._on_hotkey_action(action)

    def pet_id(self) -> str:
        """The id this pet persists under — useful for the registry
        and tests that need to verify isolation."""
        return self._pet_id

    # ---- integrations added by plugins ---------------------------------

    def add_integration(self, key: str, controller: IntegrationController) -> None:
        """Register a plugin's integration so :meth:`shutdown` stops it.

        A controller already under *key* is shut down (its enabled setting
        kept) and replaced.
        """
        self.remove_integration(key)
        self._features[key] = controller

    def remove_integration(self, key: str) -> None:
        """Stop and forget the integration under *key*, keeping its enabled setting."""
        controller = self._features.pop(key, None)
        if controller is not None:
            with best_effort("shut down a removed integration"):
                controller.shutdown()

    def integration(self, key: str) -> IntegrationController | None:
        """The integration registered under *key*, if any."""
        return self._features.get(key)

    def _restore_drivers(self) -> None:
        """Wake every persisted driver the user had running last
        session. Without this, drivers only started when the user
        opened the workspace tab (its ``_reapply_persisted_toggles``
        re-ticks the checkboxes, which fires the signal chain).
        Pets launched directly from the tray / hotkey / autorun
        went static."""
        drivers = self._settings.get("drivers", {}) or {}
        if not isinstance(drivers, dict):
            return
        # Zero-dep drivers we can flip on confidently. The rest
        # (mic_lipsync, webcam_tracking) need optional packages and
        # might fail loudly; let the user re-enable them via the
        # workspace, which has the status-label surface for the
        # "missing dep" message.
        if drivers.get("auto_idle"):
            self.set_auto_idle_enabled(True)
        if drivers.get("idle_motion"):
            self.set_idle_motion_enabled(True)
        if drivers.get("auto_blink"):
            self.set_auto_blink_enabled(True)
        if drivers.get("drag_track"):
            self.set_drag_track_enabled(True)
        if drivers.get("mouse_gaze"):
            self.set_mouse_gaze_enabled(True)
        if drivers.get("music_rhythm"):
            self.set_music_rhythm_enabled(True)
        if drivers.get("idle_minigame"):
            self.set_idle_minigame_enabled(True)

    # =====================================================================
    # Size presets
    # =====================================================================

    def set_size_preset(self, preset: str) -> None:
        size = SIZE_PRESETS.get(preset)
        if size is None:
            return
        old_centre = self.geometry().center()
        self.resize(*size)
        new_geom = self.geometry()
        new_geom.moveCenter(old_centre)
        self.setGeometry(new_geom)
        self._apply_edge_snap()
        self._persist(size_preset=preset)

    def _current_size_preset(self) -> str:
        w, h = self.width(), self.height()
        for name, (pw, ph) in SIZE_PRESETS.items():
            if (pw, ph) == (w, h):
                return name
        return "medium"

    # =====================================================================
    # Position restore
    # =====================================================================

    def _restore_position(self) -> None:   # pragma: no cover - Qt geometry
        pet_placement.restore_position(self)

    def _current_screen_name(self) -> str:   # pragma: no cover - Qt geometry
        return pet_placement.current_screen_name(self)
