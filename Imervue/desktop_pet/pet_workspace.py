"""Desktop Pet — control panel (Tab 5).

The tab itself never shows the puppet; it owns a :class:`PetWindow`
(top-level overlay) and exposes the toggles the user needs to
launch / configure / dismiss it. Single overlay per session — the
window is reused across rig swaps so the GL context and uploaded
textures survive across "open a different .puppet" actions.

The tab composes four sibling mixins ahead of ``QWidget``:
``pet_workspace_ui`` (widget construction), ``pet_workspace_files`` (rig and
pet-script loading), ``pet_workspace_toggles`` (window and driver toggles) and
``pet_workspace_hotkeys`` (the Global hotkeys group). This module keeps the
overlay lifecycle, the settings mirror and the session restore.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from Imervue.system.best_effort import best_effort
from Imervue.gui.control_tooltips import enable_control_tooltips
from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_window import PetWindow
from Imervue.desktop_pet.pet_workspace_files import (
    DEFAULT_EXAMPLE_PUPPET,
    PetWorkspaceFilesMixin,
    _resolve_bundled_example,
)
from Imervue.desktop_pet.pet_workspace_hotkeys import (
    PetWorkspaceHotkeysMixin,
    hotkey_conflict_notice,
    saved_hotkeys,
)
from Imervue.desktop_pet.pet_workspace_toggles import PetWorkspaceTogglesMixin, _set_quietly
from Imervue.desktop_pet.pet_workspace_ui import PetWorkspaceUiMixin
from Imervue.multi_language.language_wrapper import language_wrapper

logger = logging.getLogger("Imervue.desktop_pet.pet_workspace")

__all__ = [
    "DEFAULT_EXAMPLE_PUPPET",
    "PetWindow",
    "PetWorkspace",
    "_resolve_bundled_example",
    "hotkey_conflict_notice",
    "language_wrapper",
    "pet_settings",
    "saved_hotkeys",
]

# Pet settings mirrored by a Window-group checkbox (attribute names).
_WINDOW_CHECKS = {
    "click_through": "_click_through_check",
    "anchor_locked": "_anchor_check",
    "always_on_bottom": "_on_bottom_check",
    "hide_on_fullscreen": "_fullscreen_check",
    "speech_enabled": "_speech_check",
}
# Driver keys mirrored by a Live-drivers checkbox.
_DRIVER_CHECKS = {
    "auto_idle": "_idle_check",
    "idle_motion": "_idle_motion_check",
    "auto_blink": "_blink_check",
    "drag_track": "_drag_check",
    "mouse_gaze": "_gaze_check",
    "mic_lipsync": "_mic_check",
    "webcam_tracking": "_webcam_check",
}
# Drivers the pet restarts by itself when it is created; the others need an
# optional package and are started by ticking their checkbox.
_SELF_RESTORED_DRIVERS = ("auto_idle", "idle_motion", "auto_blink", "drag_track", "mouse_gaze")


class PetWorkspace(
    PetWorkspaceUiMixin,
    PetWorkspaceFilesMixin,
    PetWorkspaceTogglesMixin,
    PetWorkspaceHotkeysMixin,
    QWidget,
):
    """The control-panel tab. Owns one :class:`PetWindow`."""

    pet_created = Signal(object)
    """The :class:`PetWindow`, once, right after this tab creates it; plugins
    hear it as ``on_pet_created``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pet_window: PetWindow | None = None
        self._tray = None  # set by the main window after construction
        self._build_ui()
        self._restore_persisted_session()
        enable_control_tooltips(self)

    # ---- persisted session restore -----------------------------

    def _restore_persisted_session(self) -> None:
        """If the user's previous Imervue session had a rig and /
        or a pet script loaded, re-load them so the pet returns to
        that state. ``show_on_launch`` separately controls whether
        the overlay shows itself automatically."""
        settings = pet_settings.load()
        last_path = str(settings.get("last_rig_path", "") or "")
        # Reload the rig silently (show=False) so a persisted pet does not
        # force itself open on startup — the overlay appears only when the
        # user explicitly enabled ``show_on_launch``.
        if last_path and Path(last_path).is_file() and self.load_puppet(last_path, show=False):
            self._reapply_persisted_toggles(settings)
            if settings.get("show_on_launch"):
                self._show_check.setChecked(True)
        # PetWindow restores the script itself from settings on
        # construction; refresh the workspace's label so the UI
        # mirrors what's actually loaded.
        script_path = str(settings.get("script_path", "") or "")
        if hasattr(self, "_current_script_label"):
            self._current_script_label.setText(
                self._format_script_label(script_path),
            )

    def _reapply_persisted_toggles(self, settings: dict) -> None:
        """Re-tick the workspace's checkboxes so the visible UI
        state matches the persisted state. The pet window already
        read its own state from settings during __init__; this is
        about syncing the workspace's checkboxes."""
        drivers = settings.get("drivers", {}) or {}
        for key, checkbox in (
            ("auto_idle", self._idle_check),
            ("idle_motion", self._idle_motion_check),
            ("auto_blink", self._blink_check),
            ("drag_track", self._drag_check),
            ("mouse_gaze", self._gaze_check),
            ("mic_lipsync", self._mic_check),
            ("webcam_tracking", self._webcam_check),
        ):
            if drivers.get(key):
                checkbox.setChecked(True)

    # ---- pet-window lifecycle ----------------------------------

    def shutdown(self) -> None:
        """Release the independent overlay and tray owned by this workspace."""
        pet, self._pet_window = self._pet_window, None
        if pet is not None:
            with best_effort("shut down desktop pet", logger):
                pet.shutdown()
            with best_effort("close desktop pet", logger):
                pet.close()
                pet.deleteLater()
        tray = getattr(self, "_tray", None)
        if tray is not None:
            tray.hide()

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    def _ensure_pet_window(self) -> PetWindow:
        """Create the overlay on first need. Lazy so a user who
        never enables the tab never instantiates the GL widget."""
        if self._pet_window is None:
            self._pet_window = PetWindow()
            self._pet_window.visibility_changed.connect(
                self._on_pet_visibility_changed,
            )
            self._pet_window.setting_changed.connect(self._on_pet_setting_changed)
            # The pet restarted its zero-dependency drivers while it was being
            # built, before this connection existed.
            drivers = pet_settings.load().get("drivers", {}) or {}
            self._on_pet_setting_changed("drivers", {
                key: bool(drivers.get(key)) for key in _SELF_RESTORED_DRIVERS
            })
            self.pet_created.emit(self._pet_window)
        return self._pet_window

    def _on_pet_setting_changed(self, key: str, value) -> None:
        """Mirror a saved pet setting into its checkbox or the size combo (and
        the tray's click-through), so a change from the context menu, the tray
        or a hotkey no longer leaves the tab showing the old state."""
        if key == "drivers" and isinstance(value, dict):
            for name, attr in _DRIVER_CHECKS.items():
                if name in value:
                    _set_quietly(getattr(self, attr), value[name])
            return
        if key == "size_preset":
            index = self._size_combo.findData(str(value))
            if index >= 0:
                self._size_combo.blockSignals(True)
                self._size_combo.setCurrentIndex(index)
                self._size_combo.blockSignals(False)
            return
        attr = _WINDOW_CHECKS.get(key)
        if attr is None:
            return
        _set_quietly(getattr(self, attr), value)
        if key == "click_through" and self._tray is not None:
            self._tray.sync_click_through(bool(value))

    def pet_window(self) -> PetWindow | None:
        """Test hook — returns the overlay if it's been created."""
        return self._pet_window

    def attach_tray(self, tray) -> None:
        """Workspace doesn't own the tray (the main window does),
        but it does need a back-reference so dock toggles can mirror
        into the tray menu's state. Optional — main window calls it
        after construction; tests skip it."""
        self._tray = tray
