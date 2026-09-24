"""The desktop pet's live-driver and integration toggles.

``PetWindow`` exposes one ``set_*_enabled`` / ``*_enabled`` pair per feature
(auto blink, lip-sync, webcam tracking, hotkeys, OBS / Twitch hooks, virtual
camera, LLM dialogue, music rhythm, idle minigame, notifications, webhook,
drop shadow, click SFX, mouse gaze). Each one only forwards to the controller
that owns the feature and persists the choice, so they live together here and
``PetWindow`` mixes them in. The controllers themselves are built by
``PetWindow._init_drivers_and_voice`` / ``_init_feature_controllers``.
"""
from __future__ import annotations

import logging

from Imervue.desktop_pet.click_sfx import EVENT_NOTIFY as SFX_NOTIFY
from Imervue.desktop_pet.hotkey_manager import (
    ACTION_SPEAK_NOW,
    ACTION_TOGGLE_CLICK_THROUGH,
    ACTION_TOGGLE_LOCK,
    ACTION_TOGGLE_VISIBLE,
)

logger = logging.getLogger("Imervue.desktop_pet.pet_window")


class PetFeatureTogglesMixin:
    """Feature toggles of :class:`~Imervue.desktop_pet.pet_window.PetWindow`."""

    def set_auto_blink_enabled(self, enabled: bool) -> None:
        self._input_engine.set_blink_enabled(bool(enabled))
        self._persist_driver("auto_blink", bool(enabled))

    def set_auto_idle_enabled(self, enabled: bool) -> None:
        self._canvas_drivers.set_auto_idle_enabled(bool(enabled))
        self._persist_driver("auto_idle", bool(enabled))

    def set_mic_lipsync_enabled(self, enabled: bool) -> bool:
        ok = bool(self._input_engine.set_lipsync_enabled(bool(enabled)))
        self._persist_driver("mic_lipsync", bool(enabled and ok))
        return ok

    def set_webcam_tracking_enabled(self, enabled: bool) -> bool:
        ok = self._canvas_drivers.set_webcam_tracking_enabled(bool(enabled))
        self._persist_driver("webcam_tracking", bool(enabled and ok))
        return ok

    def set_drag_track_enabled(self, enabled: bool) -> None:
        self._input_engine.set_drag_enabled(bool(enabled))
        self._persist_driver("drag_track", bool(enabled))

    def set_hotkeys_enabled(self, enabled: bool, bindings: dict | None = None) -> bool:
        """Toggle the global-hotkey listener (see HotkeyController).
        ``bindings`` overrides the persisted map; ``None`` reads
        settings. ``False`` when the dep / OS hook is unavailable."""
        return self._features["hotkeys"].set_enabled(enabled, bindings)

    def hotkeys_enabled(self) -> bool:
        return self._features["hotkeys"].is_enabled()

    def _persisted_bindings(self) -> dict[str, str]:
        """Merge persisted overrides on top of the module defaults
        so a user who saved only one custom binding keeps the others."""
        return self._features["hotkeys"].persisted_bindings()

    def _on_hotkey_action(self, action: str) -> None:
        """Route a hotkey hit to the matching toggle. Lives in
        :class:`PetWindow` because every action needs window-state
        access (visibility, click-through, anchor)."""
        if action == ACTION_TOGGLE_VISIBLE:
            if self.isVisible():
                self.hide()
            else:
                self.show()
        elif action == ACTION_TOGGLE_LOCK:
            self.set_anchor_locked(not self._anchor_locked)
        elif action == ACTION_TOGGLE_CLICK_THROUGH:
            self.set_click_through(not self._click_through)
        elif action == ACTION_SPEAK_NOW:
            line = (
                self._script_engine.pick_time_of_day_greeting()
                or self._script_engine.pick_greeting()
            )
            if line and self._speech_enabled:
                self._show_speech(line)

    def set_obs_hook_enabled(self, enabled: bool) -> bool:
        """Connect / disconnect the OBS event listener (see
        ObsHookController). ``False`` when the dep / connection failed."""
        return self._features["obs"].set_enabled(enabled)

    def obs_hook_enabled(self) -> bool:
        return self._features["obs"].is_enabled()

    def set_twitch_hook_enabled(self, enabled: bool) -> bool:
        """Connect / disconnect the Twitch chat listener (see
        TwitchHookController). ``False`` when config / handshake failed."""
        return self._features["twitch"].set_enabled(enabled)

    def twitch_hook_enabled(self) -> bool:
        return self._features["twitch"].is_enabled()

    def set_virtual_camera_enabled(self, enabled: bool) -> bool:
        """Toggle the system virtual camera output. ``False`` when
        ``pyvirtualcam`` / a driver is missing (see PetCanvasDrivers)."""
        if enabled:
            ok = self._canvas_drivers.set_virtual_camera_enabled(True)
            self._persist(virtual_camera_enabled=bool(ok))
            return ok
        self._canvas_drivers.set_virtual_camera_enabled(False)
        self._persist(virtual_camera_enabled=False)
        return True

    def virtual_camera_enabled(self) -> bool:
        return self._canvas_drivers.virtual_camera_enabled()

    def set_llm_dialogue_enabled(self, enabled: bool) -> bool:
        """Toggle LLM-backed speech generation (see
        LlmDialogueController). ``False`` when the saved base URL is
        invalid; connection failures only surface later, per request."""
        return self._llm.set_enabled(enabled)

    def llm_dialogue_enabled(self) -> bool:
        return self._llm.is_enabled()

    def _on_llm_line(self, line: str) -> None:   # pragma: no cover - Qt UI
        """Surface a fresh LLM line only if the user still wants LLM
        speech — a stale in-flight reply after disable is discarded."""
        if not self._speech_enabled or not self.llm_dialogue_enabled():
            return
        if not line:
            return
        self._show_speech(line)

    def _on_llm_failed(self, reason: str) -> None:   # pragma: no cover - Qt UI
        """Log + fall through — the scripted line already showed
        synchronously on click, so the pet just keeps it."""
        logger.info("llm dialogue failed (%s); keeping scripted line", reason)

    def set_music_rhythm_enabled(self, enabled: bool) -> bool:
        """Toggle the system-audio rhythm driver (see
        MusicRhythmController). ``False`` when the dep / loopback is
        unavailable."""
        return self._music_rhythm.set_enabled(enabled)

    def music_rhythm_enabled(self) -> bool:
        return self._music_rhythm.is_enabled()

    def set_idle_minigame_enabled(self, enabled: bool) -> None:
        """Toggle the idle minigame (phantom curiosity + yawn /
        sleep escalation). Independent of other drivers."""
        self._idle_minigame.set_enabled(enabled)

    def idle_minigame_enabled(self) -> bool:
        return self._idle_minigame.is_enabled()

    def _notify_user_activity(self) -> None:   # pragma: no cover - Qt UI
        """Reset the idle clock — pet window mouse / drag handlers
        call this so the minigame knows the user is still there."""
        self._idle_minigame.notify_activity()

    def set_windows_notifications_enabled(self, enabled: bool) -> bool:
        """Toggle the Windows toast notification listener (see
        WindowsNotificationController). ``False`` covers missing winrt,
        non-Windows, denied permission, or registration failure."""
        return self._features["windows_notifications"].set_enabled(enabled)

    def windows_notifications_enabled(self) -> bool:
        return self._features["windows_notifications"].is_enabled()

    def speak_notification(self, line: str) -> None:   # pragma: no cover - Qt UI
        """Route a notification's title through the speech bubble +
        SFX. Called by the notification controller; bypasses the
        script engine because the notification text already carries
        its own content (no generic-greeting fallback)."""
        if not self._speech_enabled or not line:
            return
        self._show_speech(line)
        self._play_sfx(SFX_NOTIFY)

    def set_webhook_enabled(self, enabled: bool) -> bool:
        """Toggle the localhost HTTP webhook receiver (see
        WebhookController). ``False`` when the bind failed (port in
        use, OS refusal)."""
        return self._features["webhook"].set_enabled(enabled)

    def webhook_enabled(self) -> bool:
        return self._features["webhook"].is_enabled()

    def set_pet_shadow_enabled(self, enabled: bool) -> None:
        """Toggle the drop shadow + persist. Live update — the next
        canvas paint reflects the new state."""
        self._shadow.set_enabled(enabled)

    def pet_shadow_enabled(self) -> bool:
        return self._shadow.is_enabled()

    def set_pet_shadow_opacity(self, value: float) -> None:
        self._shadow.set_opacity(value)

    def set_pet_shadow_scale(self, value: float) -> None:
        self._shadow.set_scale(value)

    def set_click_sfx_enabled(self, enabled: bool) -> None:
        """Toggle the click SFX subsystem. Paths and volume are
        read from settings each time the player is configured —
        the workspace edit roundtrips through here."""
        self._click_sfx_ctl.set_enabled(enabled)

    def click_sfx_enabled(self) -> bool:
        return self._click_sfx_ctl.is_enabled()

    def _play_sfx(self, event: str) -> None:
        """Best-effort SFX play. No-op when the subsystem is off
        or the event has no configured path."""
        self._click_sfx_ctl.play(event)

    def set_mouse_gaze_enabled(self, enabled: bool) -> None:
        self._canvas_drivers.set_mouse_gaze_enabled(bool(enabled))
        self._persist_driver("mouse_gaze", bool(enabled))
