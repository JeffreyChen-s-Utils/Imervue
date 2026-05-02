"""Frame-animation timeline — pure-numpy model.

A simple stop-motion model: the timeline holds an ordered list of
HxWx4 RGBA "frames" (each frame is a flattened canvas snapshot),
plus a current-frame pointer and a target FPS. The dock UI
(:mod:`Imervue.paint.animation_dock`) drives this model and routes
to Qt for thumbnails + playback.

Each frame is a self-contained snapshot — no per-frame layer stack.
That keeps the engineering tight: "add frame" = copy the canvas
composite; "load frame" = paste the buffer back; playback = cycle
the pointer at the documented FPS.

Pure numpy / Qt-free so the timeline can be exercised in unit tests
without a display server.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np

DEFAULT_FPS = 12
FPS_MIN = 1
FPS_MAX = 60
MAX_FRAMES = 999   # safety cap so a runaway loop can't OOM


@dataclass
class Frame:
    """A single timeline entry — a flattened RGBA snapshot."""

    image: np.ndarray   # HxWx4 uint8 RGBA

    def __post_init__(self) -> None:
        if (
            self.image.ndim != 3
            or self.image.shape[2] != 4
            or self.image.dtype != np.uint8
        ):
            raise ValueError(
                f"frame image must be HxWx4 uint8 RGBA, got "
                f"{self.image.shape} {self.image.dtype}",
            )


@dataclass
class AnimationTimeline:
    """Mutable container for an ordered list of :class:`Frame`."""

    frames: list[Frame] = field(default_factory=list)
    current_index: int = 0
    fps: int = DEFAULT_FPS

    def __post_init__(self) -> None:
        self._clamp_fps()
        self._clamp_index()

    # ---- mutation ------------------------------------------------------

    def add_frame(self, image: np.ndarray) -> int:
        """Append a frame to the end of the list and return its index."""
        if len(self.frames) >= MAX_FRAMES:
            raise ValueError(
                f"timeline already at the {MAX_FRAMES}-frame cap",
            )
        self.frames.append(Frame(image=image.copy()))
        self.current_index = len(self.frames) - 1
        return self.current_index

    def insert_frame(self, image: np.ndarray, index: int) -> int:
        """Insert ``image`` at ``index`` (clamped to valid range)."""
        if len(self.frames) >= MAX_FRAMES:
            raise ValueError(
                f"timeline already at the {MAX_FRAMES}-frame cap",
            )
        i = max(0, min(int(index), len(self.frames)))
        self.frames.insert(i, Frame(image=image.copy()))
        self.current_index = i
        return i

    def remove_frame(self, index: int) -> bool:
        """Drop the frame at ``index``. Returns ``True`` on success.

        Refuses to remove the last frame — a timeline must always
        hold at least one frame so the dock has something to show.
        """
        if not 0 <= index < len(self.frames):
            return False
        if len(self.frames) <= 1:
            return False
        del self.frames[index]
        self._clamp_index()
        return True

    def replace_frame(self, image: np.ndarray, index: int) -> bool:
        """Overwrite ``index`` with a fresh snapshot of ``image``."""
        if not 0 <= index < len(self.frames):
            return False
        self.frames[index] = Frame(image=image.copy())
        return True

    def set_current_index(self, index: int) -> bool:
        """Move the playhead to ``index`` if it's a valid frame slot."""
        if not 0 <= index < len(self.frames):
            return False
        if self.current_index == index:
            return False
        self.current_index = index
        return True

    def advance(self, *, loop: bool = True) -> int:
        """Move the playhead forward by one frame.

        With ``loop=True`` (default) the index wraps; with ``loop=False``
        the playhead clamps at the last frame. Returns the new index.
        """
        if not self.frames:
            return 0
        nxt = self.current_index + 1
        if nxt >= len(self.frames):
            nxt = 0 if loop else len(self.frames) - 1
        self.current_index = nxt
        return self.current_index

    def set_fps(self, fps: int) -> int:
        """Set the playback FPS, clamped to ``[FPS_MIN, FPS_MAX]``."""
        self.fps = max(FPS_MIN, min(FPS_MAX, int(fps)))
        return self.fps

    # ---- access --------------------------------------------------------

    def __len__(self) -> int:
        return len(self.frames)

    def current_frame(self) -> Frame | None:
        if not self.frames:
            return None
        return self.frames[self.current_index]

    def previous_frame(self) -> Frame | None:
        """Return the frame just before the current one, or ``None``.

        Used by the onion-skin overlay so the artist sees the
        previous keyframe ghosted under the active canvas.
        """
        if len(self.frames) <= 1 or self.current_index <= 0:
            return None
        return self.frames[self.current_index - 1]

    def frame_at(self, index: int) -> Frame | None:
        if not 0 <= index < len(self.frames):
            return None
        return self.frames[index]

    # ---- internals -----------------------------------------------------

    def _clamp_fps(self) -> None:
        self.fps = max(FPS_MIN, min(FPS_MAX, int(self.fps)))

    def _clamp_index(self) -> None:
        if not self.frames:
            self.current_index = 0
            return
        self.current_index = max(
            0, min(int(self.current_index), len(self.frames) - 1),
        )


def thumbnail_for(frame: Frame, *, size: int = 64) -> np.ndarray:
    """Return a fast nearest-neighbour thumbnail of ``frame.image``.

    Used by the dock to populate the timeline strip without going
    through Qt's smooth-scaling path (cheap on big canvases). The
    output is HxWx4 uint8 RGBA, ``size``×``size`` at most.
    """
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    h, w = frame.image.shape[:2]
    if h == 0 or w == 0:
        return np.zeros((size, size, 4), dtype=np.uint8)
    target_h = min(size, h)
    target_w = min(size, w)
    if h <= target_h and w <= target_w:
        return frame.image
    ys = np.linspace(0, h - 1, target_h).astype(np.int32)
    xs = np.linspace(0, w - 1, target_w).astype(np.int32)
    return frame.image[ys][:, xs]


def from_canvas_snapshots(images: Iterable[np.ndarray]) -> AnimationTimeline:
    """Build a fresh timeline from an ordered iterable of RGBA buffers."""
    timeline = AnimationTimeline()
    for img in images:
        timeline.add_frame(img)
    timeline.current_index = 0
    return timeline
