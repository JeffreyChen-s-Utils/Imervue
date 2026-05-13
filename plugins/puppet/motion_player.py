"""Qt playback driver for ``.puppet`` motions.

A :class:`MotionPlayer` owns a QTimer and a bound :class:`PuppetCanvas`.
While playing, every tick samples the current motion at ``elapsed``
seconds, pushes each track's value into the canvas via
``set_parameter_value``, and the renderer re-runs the deformer chain.

Pure-Qt — no GL — so tests can poke the player under ``qapp`` without
a display.

**Fade-in / fade-out.** When a new motion is bound while a previous
one is active, the player smoothly interpolates each parameter from
the previous canvas value into the new motion's sampled value over
``motion.fade_in_duration`` seconds (or
:attr:`MotionPlayer.default_fade_in` when the motion doesn't carry
its own override). Stopping a motion with ``fade_out_duration > 0``
runs a symmetric ease back to each parameter's default. Both default
to ``0.0`` on freshly-constructed players so behaviour stays snap
unless callers opt in — keeps the existing per-motion-snap tests
green.
"""
from __future__ import annotations

import logging
import secrets
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, QUrl, Signal

from puppet.document import Motion
from puppet.motion_sampler import sample_motion

if TYPE_CHECKING:
    from puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.motion_player")

_PLAYBACK_FPS: int = 60


class MotionPlayer(QObject):
    """Drives a :class:`Motion` against a :class:`PuppetCanvas`."""

    state_changed = Signal()
    """Fires whenever play / stop / loop / time changes — UI listens
    so transport controls reflect current state."""

    def __init__(self, canvas: PuppetCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._motion: Motion | None = None
        self._loop: bool = True
        self._is_playing: bool = False
        self._elapsed: float = 0.0
        self._wall_anchor: float = 0.0
        # Fade-in state. Active while ``_fade_in_total > 0`` and the
        # motion has been playing for less than that duration.
        self._fade_in_total: float = 0.0
        self._fade_source: dict[str, float] = {}
        # Fade-out state. Active between ``stop()`` with a fade and
        # the moment the fade completes.
        self._fading_out: bool = False
        self._fade_out_total: float = 0.0
        self._fade_out_anchor: float = 0.0
        self._fade_out_source: dict[str, float] = {}
        self._fade_out_target: dict[str, float] = {}
        # Per-player defaults so workspaces can opt in to Live2D-style
        # fades without needing every motion to carry the field.
        self._default_fade_in: float = 0.0
        self._default_fade_out: float = 0.0
        # QSoundEffect lazily created when a motion with a sound_path
        # actually plays — keeps the import-time cost zero when the
        # workspace never touches audio.
        self._sound_effect = None
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _PLAYBACK_FPS))
        self._timer.timeout.connect(self._on_tick)

    # ---- public --------------------------------------------------------

    def set_motion(self, motion: Motion | None) -> None:
        """Bind a motion. Stops playback and resets time so a fresh
        motion always starts at 0. Captures the current canvas
        parameter values as the fade source so the first tick blends
        from where the rig already was — when both the previous and
        new motion have fade configured."""
        had_previous_motion = self._motion is not None
        previous_values = (
            dict(self._canvas.parameter_values()) if had_previous_motion else {}
        )
        # Snap-stop so the fade-out machinery doesn't tail into the new
        # motion's fade-in. We reset state directly rather than calling
        # the public stop() which would emit before we've bound the
        # new motion — that race confuses listeners in transport UI.
        self._is_playing = False
        self._timer.stop()
        self._elapsed = 0.0
        self._reset_fade_state()
        self._motion = motion
        if motion is not None and had_previous_motion:
            effective_in = self._effective_fade_in(motion)
            if effective_in > 0.0:
                self._fade_in_total = effective_in
                self._fade_source = previous_values
        self.state_changed.emit()

    def motion(self) -> Motion | None:
        return self._motion

    def is_playing(self) -> bool:
        return self._is_playing

    def is_fading_out(self) -> bool:
        return self._fading_out

    def elapsed(self) -> float:
        return self._elapsed

    def duration(self) -> float:
        return float(self._motion.duration) if self._motion is not None else 0.0

    def set_loop(self, loop: bool) -> None:
        self._loop = bool(loop)
        self.state_changed.emit()

    def loop(self) -> bool:
        return self._loop

    def set_default_fade(self, fade_in: float, fade_out: float) -> None:
        """Configure per-player fade durations applied to any motion
        whose own ``fade_in_duration`` / ``fade_out_duration`` is
        zero. Workspaces that want Live2D-style transitions on
        non-Cubism motions call this once after constructing the
        player."""
        self._default_fade_in = max(0.0, float(fade_in))
        self._default_fade_out = max(0.0, float(fade_out))

    def default_fade_in(self) -> float:
        return self._default_fade_in

    def default_fade_out(self) -> float:
        return self._default_fade_out

    def play_group(
        self, group_name: str, motions: list[Motion],
    ) -> Motion | None:
        """Bind and play a random motion drawn from ``motions`` whose
        ``Motion.group`` equals ``group_name``. Returns the motion that
        was picked, or ``None`` when no candidates matched.

        ``secrets.choice`` (not ``random.choice``) so the pick survives
        bandit's "non-crypto-grade random" lint — the choice itself
        doesn't need crypto-grade entropy, but the project's
        ``B311`` policy forbids ``random`` outside test code."""
        candidates = [m for m in motions if m.group == group_name]
        if not candidates:
            return None
        picked = candidates[0] if len(candidates) == 1 else secrets.choice(candidates)
        self.set_motion(picked)
        self.play()
        return picked

    def play(self) -> None:
        if self._motion is None or self._is_playing:
            return
        self._is_playing = True
        self._wall_anchor = time.monotonic() - self._elapsed
        self._timer.start()
        self._maybe_play_sound()
        self.state_changed.emit()

    def stop(self) -> None:
        """Stop the player. If the active motion has a fade-out window,
        smoothly ease parameter values back to their defaults across
        that window before fully clearing — otherwise snap to t=0
        and apply the motion's frame-0 values (legacy behaviour)."""
        if (
            not self._is_playing and self._elapsed == 0.0
            and not self._fading_out
        ):
            return
        if not self._fading_out and self._can_start_fade_out():
            self._start_fade_out()
            return
        self._snap_stop()

    def pause(self) -> None:
        if not self._is_playing:
            return
        self._is_playing = False
        self._timer.stop()
        self._stop_sound()
        self.state_changed.emit()

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

    # ---- fade-out helpers ----------------------------------------------

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

    # ---- sound playback ------------------------------------------------

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
