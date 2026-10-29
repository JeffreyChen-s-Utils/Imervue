"""Playhead for :class:`MotionPlayer`: seek, step, timer tick and frame application.

Each applied frame samples the bound motion and writes the batch to the canvas,
blending from the captured fade source while a fade-in window is open.
"""
from __future__ import annotations

import time

from Imervue.puppet.motion_sampler import sample_motion


class MotionPlayerTimelineMixin:
    """Seek / step / tick and the per-frame canvas write."""

    def seek(self, t_sec: float) -> None:
        """Jump to ``t_sec`` and apply that frame to the canvas. Keeps
        playback running if it was running."""
        was_playing = self._is_playing
        self._elapsed = max(0.0, float(t_sec))
        if self._motion is not None and not self._loop:
            self._elapsed = min(self._elapsed, self.duration())
        self._apply_at(self._elapsed)
        if was_playing:
            self._wall_anchor = time.monotonic() - self._elapsed
        self.state_changed.emit()

    def step(self, dt: float) -> None:
        """Advance the playhead by ``dt`` seconds without using the
        timer. Used by tests to drive deterministic frames."""
        self.seek(self._elapsed + dt)

    # ---- timer ---------------------------------------------------------

    def _on_tick(self) -> None:
        if self._fading_out:
            self._advance_fade_out()
            return
        if self._motion is None:
            self.pause()
            return
        now = time.monotonic()
        self._elapsed = now - self._wall_anchor
        if not self._loop and self._elapsed >= self.duration():
            self._elapsed = self.duration()
            self._apply_at(self._elapsed)
            self.pause()
            return
        self._apply_at(self._elapsed)

    def _apply_at(self, t_sec: float) -> None:
        if self._motion is None:
            return
        sampled = sample_motion(self._motion, t_sec, loop=self._loop)
        if self._fade_in_total > 0.0 and t_sec < self._fade_in_total:
            progress = max(0.0, min(1.0, t_sec / self._fade_in_total))
            batch = {
                pid: self._fade_source.get(pid, value) + (
                    value - self._fade_source.get(pid, value)
                ) * progress
                for pid, value in sampled.items()
            }
            self._canvas.set_parameter_values(batch)
            return
        if self._fade_in_total > 0.0 and t_sec >= self._fade_in_total:
            # First post-fade application — clear the fade so future
            # seeks back into the fade window don't reintroduce it.
            self._fade_in_total = 0.0
            self._fade_source = {}
        self._canvas.set_parameter_values(sampled)
