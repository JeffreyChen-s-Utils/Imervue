"""Desktop Pet tab — window toggles and live-driver checkboxes.

The slots behind the Window and Live drivers groups: each forwards its
checkbox / slider / combo to the overlay's setter, and the optional-dependency
drivers (mic lip-sync, webcam tracking) untick themselves quietly with a status
hint when their package is missing. Also home of the tab's shared ``_tr`` and
``_set_quietly`` helpers.
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox

from Imervue.desktop_pet import settings as pet_settings
from Imervue.multi_language.language_wrapper import language_wrapper


def _tr(key: str, default: str) -> str:
    """Tiny shortcut to keep call sites readable. Every UI
    string on the tab goes through the wrapper so the labels
    swap when the user changes language at runtime."""
    return language_wrapper.language_word_dict.get(key, default)


def _set_quietly(box: QCheckBox, checked: bool) -> None:
    """Tick or untick ``box`` without running its toggled handler."""
    box.blockSignals(True)
    try:
        box.setChecked(bool(checked))
    finally:
        box.blockSignals(False)


class PetWorkspaceTogglesMixin:
    """Window / driver toggle slots of :class:`PetWorkspace`."""

    # ---- visibility --------------------------------------------

    def _on_show_toggled(self, checked: bool) -> None:
        window = self._ensure_pet_window()
        if checked:
            window.show()
        else:
            window.hide()

    def _on_pet_visibility_changed(self, visible: bool) -> None:
        # Quietly, so the toggled signal doesn't feed back into
        # ``_on_show_toggled``.
        _set_quietly(self._show_check, visible)
        # Keep the tray's checkable "Show pet" in sync too. Without this its state
        # went stale, so the next tray click toggled from the wrong value and the
        # first click was wasted (a "hide" that ran show()).
        if self._tray is not None:
            self._tray.sync_visibility(visible)

    @staticmethod
    def _on_show_on_launch_toggled(checked: bool) -> None:
        """Remember whether the overlay opens with Imervue (``show_on_launch``)."""
        pet_settings.update(show_on_launch=bool(checked))

    def _on_click_through_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_click_through(bool(checked))
        if self._tray is not None:
            self._tray.sync_click_through(bool(checked))

    def _on_anchor_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_anchor_locked(bool(checked))

    def _on_always_on_bottom_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_always_on_bottom(bool(checked))

    def _on_fullscreen_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_hide_on_fullscreen(bool(checked))

    def _on_speech_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_speech_enabled(bool(checked))

    def _on_opacity_changed(self, percent: int) -> None:
        value = max(10, min(100, int(percent))) / 100.0
        self._opacity_label.setText(f"{int(value * 100)}%")
        self._ensure_pet_window().set_pet_opacity(value)

    def _on_snap_changed(self, px: int) -> None:
        self._ensure_pet_window().set_snap_threshold(int(px))

    def _on_size_changed(self, preset: str) -> None:
        if self._pet_window is None:
            return
        self._pet_window.set_size_preset(preset)

    # ---- drivers -----------------------------------------------

    def _on_idle_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_auto_idle_enabled(bool(checked))

    def _on_idle_motion_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_idle_motion_enabled(bool(checked))

    def _on_blink_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_auto_blink_enabled(bool(checked))

    def _on_drag_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_drag_track_enabled(bool(checked))

    def _on_gaze_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_mouse_gaze_enabled(bool(checked))

    def _on_mic_toggled(self, checked: bool) -> None:
        ok = self._ensure_pet_window().set_mic_lipsync_enabled(bool(checked))
        if checked and not ok:
            self._status.setText(
                _tr(
                    "desktop_pet_mic_missing",
                    "Mic lip-sync needs sounddevice — pip install sounddevice",
                ),
            )
            _set_quietly(self._mic_check, False)

    def _on_webcam_toggled(self, checked: bool) -> None:
        ok = self._ensure_pet_window().set_webcam_tracking_enabled(bool(checked))
        if checked and not ok:
            self._status.setText(
                _tr(
                    "desktop_pet_webcam_missing",
                    "Webcam tracking needs opencv-python + mediapipe",
                ),
            )
            _set_quietly(self._webcam_check, False)
