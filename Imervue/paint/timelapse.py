"""Time-lapse export — replay a recording and snapshot each step.

The action recorder (:mod:`Imervue.paint.action_recorder`) captures a
sequence of dispatcher events; this module is the bridge that turns
such a recording into a stream of composite frames suitable for
animation export. The flow is:

* Caller builds a fresh starting :class:`PaintDocument` (the same
  state the recording originally began against).
* Caller passes the recording, a target callable, and the document
  to :func:`render_timelapse_frames`.
* The function walks the recording, applies each action via the
  target callable, and snapshots ``document.composite()`` after each
  step (or every Nth step when ``frame_every`` > 1).
* Caller wraps the resulting frame list into an :class:`Animation`
  via :func:`frames_to_animation` and pipes it through the existing
  :mod:`Imervue.paint.animation_export` writers.

Pure-Python — no Qt, no extra runtime dependencies. The target
callable is the same ``(kind, params) -> None`` shape the recorder
already speaks, so callers don't need a separate dispatch path for
time-lapse playback.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

from Imervue.paint.action_recorder import ActionRecording
from Imervue.paint.animation import (
    DEFAULT_FPS,
    MAX_FPS,
    MIN_FPS,
    Animation,
    AnimationFrame,
)
from Imervue.paint.document import PaintDocument

# Cap the frame budget so a recording with hundreds of thousands of
# pen-move events doesn't try to allocate gigabytes of frame buffers.
# Callers with bigger recordings should bump ``frame_every``.
MAX_TIMELAPSE_FRAMES = 4096


def render_timelapse_frames(
    recording: ActionRecording,
    target: Callable[[str, dict], None],
    document: PaintDocument,
    *,
    frame_every: int = 1,
    include_initial: bool = True,
) -> list[np.ndarray]:
    """Replay ``recording`` against ``document`` and snapshot frames.

    ``target`` receives ``(kind, params)`` for each action and is
    expected to mutate ``document`` (or whatever shared state the
    caller routes through). After each replayed action whose index
    satisfies ``index % frame_every == 0`` the function reads
    ``document.composite()`` and appends a fresh copy to the frame
    list. When ``include_initial`` is ``True`` (the default) the
    pre-replay composite seeds the list as frame 0.

    Returns the captured frames in chronological order. Raises
    :class:`ValueError` for invalid inputs and propagates the first
    target exception so a broken action shows up at the call site.
    """
    if frame_every < 1:
        raise ValueError(f"frame_every must be >= 1, got {frame_every}")

    frames: list[np.ndarray] = []
    if include_initial:
        initial = document.composite()
        if initial is not None:
            frames.append(np.ascontiguousarray(initial.copy()))

    for index, action in enumerate(recording.actions):
        target(action.kind, dict(action.params))
        if (index + 1) % frame_every != 0:
            continue
        if len(frames) >= MAX_TIMELAPSE_FRAMES:
            break
        composite = document.composite()
        if composite is None:
            continue
        frames.append(np.ascontiguousarray(composite.copy()))
    return frames


def frames_to_animation(
    frames: list[np.ndarray],
    *,
    fps: int = DEFAULT_FPS,
    name: str = "Timelapse",
) -> Animation:
    """Wrap a list of HxWx4 frames into an :class:`Animation`.

    Each frame becomes a single-layer PaintDocument inside an
    AnimationFrame whose duration is derived from ``fps``. The
    resulting Animation can be fed directly to
    :mod:`Imervue.paint.animation_export`'s GIF / WebP / APNG writers.
    """
    if not frames:
        raise ValueError("frames must be non-empty")
    if not MIN_FPS <= int(fps) <= MAX_FPS:
        raise ValueError(
            f"fps must be in [{MIN_FPS}, {MAX_FPS}], got {fps}",
        )
    if not str(name).strip():
        raise ValueError("animation name must be non-empty")
    duration_ms = max(1, int(round(1000.0 / float(fps))))
    animation_frames: list[AnimationFrame] = []
    for i, frame in enumerate(frames):
        if frame.ndim != 3 or frame.shape[2] != 4 or frame.dtype != np.uint8:
            raise ValueError(
                f"frame {i} must be HxWx4 uint8 RGBA, got shape={frame.shape}"
                f" dtype={frame.dtype}",
            )
        document = PaintDocument()
        document.load_image(np.ascontiguousarray(frame))
        animation_frames.append(AnimationFrame(
            document=document,
            name=f"{name} {i + 1}",
            duration_ms=duration_ms,
        ))
    return Animation(frames=animation_frames, fps=int(fps))
