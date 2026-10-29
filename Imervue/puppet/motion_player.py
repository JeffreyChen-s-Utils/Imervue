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

The playhead (seek / tick / frame application), the fade-out machinery and
the sound hooks live in the ``motion_player_timeline`` /
``motion_player_fade`` / ``motion_player_sound`` mixins; this module keeps the
class, its state, binding and transport.
"""
from __future__ import annotations

import logging
import secrets
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.document import Motion
from Imervue.puppet.motion_player_fade import MotionPlayerFadeMixin
from Imervue.puppet.motion_player_sound import MotionPlayerSoundMixin
from Imervue.puppet.motion_player_timeline import MotionPlayerTimelineMixin

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.motion_player")

_PLAYBACK_FPS: int = 60


class MotionPlayer(
    MotionPlayerTimelineMixin,
    MotionPlayerFadeMixin,
    MotionPlayerSoundMixin,
    QObject,
):
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
        new motion have fade configured. Looping follows the motion's own
        ``loop`` flag (a tap reaction plays once, an idle loops)."""
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
        if motion is not None:
            self._loop = bool(motion.loop)
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
        """Loop or not; the bound motion's ``loop`` flag changes with it, so a save keeps it."""
        self._loop = bool(loop)
        if self._motion is not None:
            self._motion.loop = self._loop
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
            not self._is_playing and self._elapsed <= 0.0
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
