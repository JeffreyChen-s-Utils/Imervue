"""Qt playback driver for ``.puppet`` motions.

A :class:`MotionPlayer` owns a QTimer and a bound :class:`PuppetCanvas`.
While playing, every tick samples the current motion at ``elapsed``
seconds, pushes each track's value into the canvas via
``set_parameter_value``, and the renderer re-runs the deformer chain.

Pure-Qt — no GL — so tests can poke the player under ``qapp`` without
a display.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.document import Motion
from Imervue.puppet.motion_sampler import sample_motion

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas


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
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _PLAYBACK_FPS))
        self._timer.timeout.connect(self._on_tick)

    # ---- public --------------------------------------------------------

    def set_motion(self, motion: Motion | None) -> None:
        """Bind a motion. Stops playback and resets time so a fresh
        motion always starts at 0."""
        self.stop()
        self._motion = motion
        self.state_changed.emit()

    def motion(self) -> Motion | None:
        return self._motion

    def is_playing(self) -> bool:
        return self._is_playing

    def elapsed(self) -> float:
        return self._elapsed

    def duration(self) -> float:
        return float(self._motion.duration) if self._motion is not None else 0.0

    def set_loop(self, loop: bool) -> None:
        self._loop = bool(loop)
        self.state_changed.emit()

    def loop(self) -> bool:
        return self._loop

    def play(self) -> None:
        if self._motion is None or self._is_playing:
            return
        self._is_playing = True
        self._wall_anchor = time.monotonic() - self._elapsed
        self._timer.start()
        self.state_changed.emit()

    def stop(self) -> None:
        if not self._is_playing and self._elapsed == 0.0:
            return
        self._is_playing = False
        self._timer.stop()
        self._elapsed = 0.0
        self._apply_at(0.0)
        self.state_changed.emit()

    def pause(self) -> None:
        if not self._is_playing:
            return
        self._is_playing = False
        self._timer.stop()
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
        values = sample_motion(self._motion, t_sec, loop=self._loop)
        for param_id, value in values.items():
            self._canvas.set_parameter_value(param_id, value)
