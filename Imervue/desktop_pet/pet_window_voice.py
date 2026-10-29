"""Speech bubble and scripted voice for :class:`PetWindow`.

``PetVoiceMixin`` owns the click response (scripted line first, LLM reply in
parallel), the speech-bubble toggle and display, and the user-loadable
``.petscript.json`` (load, reset, restore at startup, 1 Hz scheduled chimes).
It relies on the host window's ``_speech_enabled``, ``_speech``,
``_script_engine``, ``_settings`` and ``_llm`` attributes and its ``_persist``,
``llm_dialogue_enabled``, ``geometry`` and ``isVisible``.
"""
from __future__ import annotations

import logging
from pathlib import Path

from Imervue.desktop_pet.pet_interaction import llm_situation_tag
from Imervue.desktop_pet.pet_script import (
    PetScript,
    PetScriptEngine,
    PetScriptError,
    load_script,
)
from Imervue.desktop_pet.speech_bubble import SpeechBubble

logger = logging.getLogger("Imervue.desktop_pet.pet_window")


class PetVoiceMixin:
    """Speech-bubble and pet-script behaviour mixed into ``PetWindow``."""

    def reanchor_speech(self) -> None:   # pragma: no cover - Qt UI
        """Re-anchor the speech bubble to the current geometry — the
        interaction controller calls this mid-drag so the bubble tracks
        the pet."""
        if self._speech is not None:
            self._speech.anchor_to(self.geometry())

    def speak_click_response(
        self, area_id: str, motion_name: str | None,
    ) -> None:
        """Show the scripted speech line for a click (if speech is
        on) and fire the LLM in parallel if enabled. The scripted
        line shows immediately for snappy feedback; the LLM reply
        replaces it via ``_on_llm_line`` if/when it lands."""
        if not self._speech_enabled:
            return
        line = (
            self._script_engine.pick_for_hit_area(area_id or None)
            or self._script_engine.pick_for_motion(motion_name)
            or self._script_engine.pick_time_of_day_greeting()
            or self._script_engine.pick_greeting()
        )
        if line:
            self._show_speech(line)
        if not self.llm_dialogue_enabled():
            return
        try:
            self._llm.request_line(llm_situation_tag(area_id, motion_name))
        except ValueError:
            return

    def speak(self, line: str) -> None:
        self._show_speech(line)

    @property
    def speech_on(self) -> bool:
        return self._speech_enabled

    # =====================================================================
    # Speech bubble
    # =====================================================================

    def set_speech_enabled(self, enabled: bool) -> None:
        self._speech_enabled = bool(enabled)
        self._persist(speech_enabled=self._speech_enabled)
        if not enabled and self._speech is not None:
            self._speech.close_bubble()

    def speech_enabled(self) -> bool:
        return self._speech_enabled

    def _show_speech(self, text: str) -> None:
        # Webhook, notification and hotkey lines keep arriving while the pet is
        # hidden (hotkey, tray, hide-on-fullscreen); a bubble then would float
        # alone over whatever the pet was hidden for.
        if not self._speech_enabled or not text or not self.isVisible():
            return
        if self._speech is None:
            self._speech = SpeechBubble()
        self._speech.anchor_to(self.geometry())
        self._speech.show_message(text)

    # =====================================================================
    # Pet script (user-customisable voice)
    # =====================================================================

    def load_script_file(self, path: str | Path) -> bool:
        """Load a ``.petscript.json`` and bind it to the engine.
        Returns ``True`` on success; failure writes the path to
        the settings so the workspace can show a useful message
        but doesn't crash the pet."""
        try:
            script = load_script(path)
        except PetScriptError as exc:
            logger.warning("pet script %s failed: %s", path, exc)
            return False
        self._script_engine.set_script(script)
        self._persist(script_path=str(path))
        return True

    def reset_script_to_default(self) -> None:
        """Drop the user script and revert to the built-in
        greeting set. Clears the persisted path so the next
        launch doesn't reload the now-rejected script."""
        self._script_engine.set_script(PetScript.default())
        self._persist(script_path="")

    def script_engine(self) -> PetScriptEngine:
        """Test / advanced caller hook — exposes the engine so
        external code can read the active script without poking
        the private attribute."""
        return self._script_engine

    def _restore_persisted_script(self) -> None:
        """Apply the script the previous session ended with. A
        missing / unreadable file falls back silently to the
        default voice — the workspace's status label is the
        user-facing reporting channel."""
        path = str(self._settings.get("script_path", "") or "")
        if not path:
            return
        try:
            self._script_engine.set_script(load_script(path))
        except PetScriptError as exc:
            logger.info("ignoring stale pet script %s: %s", path, exc)

    def _on_script_tick(self) -> None:   # pragma: no cover - Qt timer
        """1 Hz heartbeat that fires any due
        :class:`ScheduledEvent` from the active script."""
        if not self._speech_enabled:
            return
        line = self._script_engine.due_scheduled_message()
        if line:
            self._show_speech(line)
