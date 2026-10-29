"""User motion recording lifecycle and document insertion."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QInputDialog,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.motion_recorder import append_motion

class PuppetMotionRecordMixin:
    def _toggle_motion_record(self, enabled: bool) -> None:
        if enabled:
            if not self._start_motion_recording():
                self._reset_toggle(self._motion_record_toggle)
        else:
            self._motion_recorder.stop()

    def _start_motion_recording(self) -> bool:
        if self._canvas.document() is None:
            return False
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("puppet_record_motion_title", "Record motion"),
            lang.get("puppet_record_motion_prompt", "Motion name:"),
            text="user_motion",
        )
        if not ok or not name.strip():
            return False
        return self._motion_recorder.start(name.strip())

    def _on_motion_recorded(self, motion) -> None:
        if motion is None:
            return
        if append_motion(self._canvas, motion):
            self._announce(
                "puppet_motion_recorded",
                "Recorded motion '{name}' ({duration:.1f}s, {tracks} tracks)",
                name=motion.name,
                duration=motion.duration,
                tracks=len(motion.tracks),
            )
