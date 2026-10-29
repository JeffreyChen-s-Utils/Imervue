"""Fade-out and fade bookkeeping for :class:`MotionPlayer`.

A stop with a fade-out window eases every captured parameter toward its
document default before the snap-stop clears playback; the effective fade
durations fall back to the player's defaults when a motion carries none.
"""
from __future__ import annotations

import time

from Imervue.puppet.document import Motion


class MotionPlayerFadeMixin:
    """Fade-out easing, snap-stop and fade state reset."""

    def _can_start_fade_out(self) -> bool:
        return (
            self._motion is not None
            and self._effective_fade_out(self._motion) > 0.0
            and bool(self._motion.tracks)
        )

    def _start_fade_out(self) -> None:
        # ``_can_start_fade_out`` is the only caller and gates on
        # ``self._motion is not None``; defensively re-check so
        # ``python -O`` (which strips asserts) still bails safely.
        if self._motion is None:
            return
        self._fade_out_total = self._effective_fade_out(self._motion)
        self._fade_out_anchor = time.monotonic()
        self._fade_out_source = dict(self._canvas.parameter_values())
        self._fade_out_target = self._fade_out_defaults_for_motion()
        self._is_playing = False
        self._fading_out = True
        if not self._timer.isActive():
            self._timer.start()
        self.state_changed.emit()

    def _advance_fade_out(self) -> None:
        elapsed = time.monotonic() - self._fade_out_anchor
        progress = (
            min(1.0, elapsed / self._fade_out_total)
            if self._fade_out_total > 0.0 else 1.0
        )
        batch = {
            pid: source + (
                self._fade_out_target.get(pid, source) - source
            ) * progress
            for pid, source in self._fade_out_source.items()
        }
        self._canvas.set_parameter_values(batch)
        if progress >= 1.0:
            self._snap_stop()

    def _fade_out_defaults_for_motion(self) -> dict[str, float]:
        doc = self._canvas.document()
        out: dict[str, float] = {}
        if doc is None or self._motion is None:
            return out
        for track in self._motion.tracks:
            param = doc.parameter(track.param_id)
            if param is not None:
                out[track.param_id] = float(param.default)
        return out

    def _snap_stop(self) -> None:
        was_fading = self._fading_out
        self._is_playing = False
        self._fading_out = False
        self._timer.stop()
        self._stop_sound()
        self._elapsed = 0.0
        self._reset_fade_state()
        if not was_fading and self._motion is not None:
            # Legacy behaviour: when stop() runs without a fade-out
            # window, the canvas snaps to the motion's frame 0. The
            # fade-out path already wrote final-frame values so it
            # skips this.
            self._apply_at(0.0)
        self.state_changed.emit()

    def _reset_fade_state(self) -> None:
        self._fade_in_total = 0.0
        self._fade_source = {}
        self._fading_out = False
        self._fade_out_total = 0.0
        self._fade_out_source = {}
        self._fade_out_target = {}

    def _effective_fade_in(self, motion: Motion) -> float:
        return float(motion.fade_in_duration) or self._default_fade_in

    def _effective_fade_out(self, motion: Motion) -> float:
        return float(motion.fade_out_duration) or self._default_fade_out
