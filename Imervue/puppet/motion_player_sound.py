"""Motion sound playback for :class:`MotionPlayer`.

A ``QSoundEffect`` is created lazily the first time a motion with a
``sound_path`` plays; missing files or a missing ``PySide6.QtMultimedia`` are
logged and never interrupt the visual timeline.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QUrl

logger = logging.getLogger("Imervue.plugin.puppet.motion_player")


class MotionPlayerSoundMixin:
    """Start, stop and lazily create the motion's sound effect."""

    def _maybe_play_sound(self) -> None:
        """If the bound motion has a ``sound_path``, start playback.
        Failures (missing file, missing QtMultimedia, codec issues) are
        logged at debug level and never raised — the motion's visual
        timeline must keep running even when audio is unavailable."""
        if self._motion is None or not self._motion.sound_path:
            return
        path = Path(self._motion.sound_path)
        if not path.is_file():
            logger.debug("motion sound %s missing on disk", path)
            return
        effect = self._ensure_sound_effect()
        if effect is None:
            return
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.play()

    def _stop_sound(self) -> None:
        if self._sound_effect is None:
            return
        try:
            self._sound_effect.stop()
        except RuntimeError as exc:
            # The C++ side may already be deleted during teardown.
            logger.debug("sound stop failed: %s", exc)

    def _ensure_sound_effect(self):
        """Lazy-create a QSoundEffect on first use. Returns ``None`` if
        ``PySide6.QtMultimedia`` isn't available — keeps the player
        usable in headless test environments without the audio module."""
        if self._sound_effect is not None:
            return self._sound_effect
        try:
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:
            logger.info("PySide6.QtMultimedia not available; motion audio disabled")
            return None
        self._sound_effect = QSoundEffect(self)
        return self._sound_effect
