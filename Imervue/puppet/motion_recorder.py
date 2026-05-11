"""Record live parameter changes into a :class:`Motion`.

The user picks "Record motion", drags sliders / uses face tracking
for as long as they want, then stops. We sample the canvas's current
parameter values at a fixed rate, then bake the captured time-series
into a Motion with linear segments — one track per parameter that
actually changed.

Two pieces:

* :class:`MotionRecorder` — Qt object owning a QTimer that grabs
  parameter snapshots at ``capture_fps``. Pause / resume / stop
  controls; emits ``finished`` with the baked Motion.
* :func:`bake_to_motion` — pure-Python: turn a parameter-vs-time
  matrix into a Motion. Useful for tests + offline pipelines.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.document import Motion, MotionSegment, MotionTrack

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.motion_recorder")

DEFAULT_CAPTURE_FPS: int = 30
_FLAT_TRACK_EPSILON: float = 1e-6


def bake_to_motion(
    name: str,
    samples: list[tuple[float, dict[str, float]]],
    *,
    loop: bool = True,
) -> Motion:
    """Turn a list of ``(time_sec, parameter_values)`` snapshots into
    a :class:`Motion`. Each parameter that varies across the timeline
    becomes one MotionTrack with linear segments between consecutive
    samples; parameters whose values stay flat for the whole take are
    dropped (no point keying ``ParamX = 0`` in a recorded motion).
    """
    if not samples:
        return Motion(name=name, duration=0.0, loop=loop, tracks=[])
    duration = float(samples[-1][0] - samples[0][0])
    base_t = samples[0][0]
    # Collect (t, value) pairs per parameter id
    by_param: dict[str, list[tuple[float, float]]] = {}
    for t, values in samples:
        rel_t = float(t - base_t)
        for pid, value in values.items():
            by_param.setdefault(pid, []).append((rel_t, float(value)))
    tracks: list[MotionTrack] = []
    for pid, points in by_param.items():
        if _is_flat(points):
            continue
        segments: list[MotionSegment] = []
        for prev, nxt in zip(points, points[1:], strict=False):
            if nxt[0] - prev[0] <= 0:
                continue
            segments.append(
                MotionSegment(type="linear", p0=prev, p1=nxt),
            )
        if segments:
            tracks.append(MotionTrack(param_id=pid, segments=segments))
    return Motion(name=name, duration=max(0.0, duration), loop=loop, tracks=tracks)


def _is_flat(points: list[tuple[float, float]]) -> bool:
    if not points:
        return True
    first = points[0][1]
    return all(abs(p[1] - first) < _FLAT_TRACK_EPSILON for p in points)


class MotionRecorder(QObject):
    """Captures parameter snapshots from a canvas into a Motion."""

    finished = Signal(object)
    """Emitted with the baked :class:`Motion` when ``stop`` is called."""

    def __init__(self, canvas: PuppetCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._capture_fps: int = DEFAULT_CAPTURE_FPS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._samples: list[tuple[float, dict[str, float]]] = []
        self._start_wall: float = 0.0
        self._motion_name: str = "recorded"
        self._loop: bool = True
        self._is_recording: bool = False

    # ---- public --------------------------------------------------------

    def is_recording(self) -> bool:
        return self._is_recording

    def start(
        self, name: str, *, fps: int = DEFAULT_CAPTURE_FPS, loop: bool = True,
    ) -> bool:
        if self._is_recording:
            return False
        if not name.strip():
            return False
        self._motion_name = name.strip()
        self._capture_fps = max(1, int(fps))
        self._loop = bool(loop)
        self._samples = []
        self._start_wall = time.monotonic()
        self._timer.setInterval(int(1000 / self._capture_fps))
        self._timer.start()
        self._is_recording = True
        # Capture an initial frame so a zero-duration motion still has at
        # least one sample.
        self._capture_one()
        return True

    def stop(self) -> Motion | None:
        if not self._is_recording:
            return None
        self._timer.stop()
        self._is_recording = False
        # Capture a final frame so the take ends on the user's last edit.
        self._capture_one()
        motion = bake_to_motion(
            self._motion_name, self._samples, loop=self._loop,
        )
        self.finished.emit(motion)
        return motion

    # ---- internals -----------------------------------------------------

    def _on_tick(self) -> None:
        if not self._is_recording:
            return
        self._capture_one()

    def _capture_one(self) -> None:
        if self._canvas.document() is None:
            return
        t = time.monotonic() - self._start_wall
        values = self._canvas.parameter_values()
        if not values:
            return
        self._samples.append((float(t), dict(values)))


def append_motion(canvas: PuppetCanvas, motion: Motion) -> bool:
    """Append (or replace by name) ``motion`` on the canvas's document
    and let any motion-aware UI rebuild itself by reloading the doc.

    Returns ``True`` on success."""
    document = canvas.document()
    if document is None:
        return False
    # Replace any existing motion of the same name (recording overwrites)
    document.motions = [m for m in document.motions if m.name != motion.name]
    document.motions.append(motion)
    canvas.load_document(document)   # forces dock rebuilds + parameter reset
    return True
