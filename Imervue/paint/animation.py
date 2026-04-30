"""Minimal animation timeline + onion-skin compositor.

The Paint workspace ships static painting up through 12d. This
module adds the bare-bones data model the dispatcher needs to
support frame-based animation:

* :class:`AnimationFrame` — a per-frame :class:`PaintDocument` with
  a display name and a duration in milliseconds.
* :class:`Animation` — ordered list of frames with active-frame
  pointer, frame rate, and looping flag.
* :func:`composite_with_onion_skin` — render the active frame onto
  a target buffer with N before / N after ghost-frames at reduced
  opacity, optionally tinted (red for past, green for future,
  matching the convention every paint app shares).

Pure numpy / Qt-free so the data layer can be tested without a
Qt application. The UI timeline widget that plays this back lives
above this module — the helpers here only know how to *render*
the active state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from Imervue.paint.compositing import composite_layer_pair
from Imervue.paint.document import PaintDocument

DEFAULT_FRAME_DURATION_MS = 100
MIN_FRAME_DURATION_MS = 1
MAX_FRAME_DURATION_MS = 60_000

DEFAULT_FPS = 12
MIN_FPS = 1
MAX_FPS = 120

# Onion-skin defaults — values below 1 produce a falloff per frame
# distance, so frames further from the active one fade into the
# background instead of stacking solid.
DEFAULT_BEFORE_TINT = (220, 100, 100)
DEFAULT_AFTER_TINT = (100, 200, 120)
DEFAULT_OPACITY_STEP = 0.4


@dataclass
class AnimationFrame:
    """One animation frame — a PaintDocument plus per-frame metadata."""

    document: PaintDocument
    name: str = "Frame"
    duration_ms: int = DEFAULT_FRAME_DURATION_MS

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("frame name must be non-empty")
        self.duration_ms = max(
            MIN_FRAME_DURATION_MS,
            min(MAX_FRAME_DURATION_MS, int(self.duration_ms)),
        )


@dataclass
class Animation:
    """Ordered list of :class:`AnimationFrame` plus playback state."""

    frames: list[AnimationFrame] = field(default_factory=list)
    active_index: int = 0
    fps: int = DEFAULT_FPS
    looping: bool = True

    def __post_init__(self) -> None:
        self.fps = max(MIN_FPS, min(MAX_FPS, int(self.fps)))
        self.active_index = max(
            0, min(int(self.active_index), max(0, len(self.frames) - 1)),
        )

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    def active_frame(self) -> AnimationFrame | None:
        if not self.frames:
            return None
        return self.frames[self.active_index]

    def add_frame(self, frame: AnimationFrame, *, after_active: bool = True) -> int:
        """Insert ``frame`` after the active one (or at the end). Returns
        the index of the new frame."""
        insert_at = (
            self.active_index + 1
            if after_active and self.frames
            else len(self.frames)
        )
        insert_at = min(insert_at, len(self.frames))
        self.frames.insert(insert_at, frame)
        self.active_index = insert_at
        return insert_at

    def remove_active_frame(self) -> bool:
        """Drop the active frame (if there are >= 2) and shift the active
        pointer one step back. Returns ``True`` if a frame was removed."""
        if len(self.frames) <= 1:
            return False
        del self.frames[self.active_index]
        self.active_index = max(0, self.active_index - 1)
        return True

    def set_active_index(self, index: int) -> None:
        if not 0 <= index < len(self.frames):
            raise IndexError(f"frame index {index} out of range")
        self.active_index = index


# ---------------------------------------------------------------------------
# Onion skin
# ---------------------------------------------------------------------------


def tween_frames(
    animation: Animation,
    n_inbetweens: int,
    *,
    key_indices: list[int] | None = None,
) -> Animation:
    """Insert ``n_inbetweens`` cross-faded frames between each pair of
    keys.

    By default every frame is treated as a key. ``key_indices`` (when
    supplied) lets the caller pick a subset — useful for "I drew
    poses on frames 0, 5, 10; fill in between" workflows.

    Each inbetween is a single-layer :class:`PaintDocument` whose
    image is the linear cross-fade of the two surrounding keys'
    composites. Returns a fresh :class:`Animation`; the input is not
    mutated.

    ``n_inbetweens = 0`` short-circuits to a copy of the input
    (animation length unchanged); negative values raise.
    """
    if n_inbetweens < 0:
        raise ValueError(
            f"n_inbetweens must be >= 0, got {n_inbetweens!r}",
        )
    if not animation.frames or n_inbetweens == 0:
        return Animation(
            frames=list(animation.frames),
            fps=animation.fps,
            active_index=animation.active_index,
            looping=animation.looping,
        )
    if key_indices is None:
        keys = list(range(len(animation.frames)))
    else:
        keys = sorted({
            int(i) for i in key_indices
            if 0 <= int(i) < len(animation.frames)
        })
    if not keys:
        return Animation(
            frames=list(animation.frames),
            fps=animation.fps,
            active_index=animation.active_index,
            looping=animation.looping,
        )

    new_frames: list[AnimationFrame] = []
    for i, key_idx in enumerate(keys):
        new_frames.append(animation.frames[key_idx])
        if i == len(keys) - 1:
            continue
        next_key_idx = keys[i + 1]
        key_a = animation.frames[key_idx]
        key_b = animation.frames[next_key_idx]
        for j in range(1, n_inbetweens + 1):
            t = j / (n_inbetweens + 1)
            inbetween_doc = _interpolate_documents(
                key_a.document, key_b.document, t,
            )
            new_frames.append(AnimationFrame(
                document=inbetween_doc,
                name=f"tween {j}/{n_inbetweens + 1}",
                duration_ms=key_a.duration_ms,
            ))
    return Animation(
        frames=new_frames,
        fps=animation.fps,
        active_index=min(animation.active_index, len(new_frames) - 1),
        looping=animation.looping,
    )


def _interpolate_documents(
    doc_a: PaintDocument,
    doc_b: PaintDocument,
    t: float,
) -> PaintDocument:
    """Build a fresh single-layer :class:`PaintDocument` that is the
    linear cross-fade of ``doc_a`` and ``doc_b``'s composites at ``t``."""
    composite_a = doc_a.composite()
    composite_b = doc_b.composite()
    if composite_a is None and composite_b is None:
        empty_doc = PaintDocument()
        return empty_doc
    shape_a = doc_a.shape
    shape_b = doc_b.shape
    target_shape = shape_a or shape_b
    if target_shape is None:
        return PaintDocument()
    if composite_a is None:
        h, w = target_shape
        composite_a = np.zeros((h, w, 4), dtype=np.uint8)
    if composite_b is None:
        h, w = target_shape
        composite_b = np.zeros((h, w, 4), dtype=np.uint8)
    if composite_a.shape != composite_b.shape:
        raise ValueError(
            f"key documents have different shapes "
            f"({composite_a.shape} vs {composite_b.shape}); "
            f"can't tween mismatched canvases",
        )
    blended = (
        composite_a.astype(np.float32) * (1.0 - float(t))
        + composite_b.astype(np.float32) * float(t)
    )
    blended_u8 = np.clip(blended, 0.0, 255.0).astype(np.uint8)
    out = PaintDocument()
    out.load_image(blended_u8)
    return out


def composite_with_onion_skin(
    animation: Animation,
    *,
    before_count: int = 1,
    after_count: int = 1,
    before_tint: tuple[int, int, int] = DEFAULT_BEFORE_TINT,
    after_tint: tuple[int, int, int] = DEFAULT_AFTER_TINT,
    opacity_step: float = DEFAULT_OPACITY_STEP,
) -> np.ndarray | None:
    """Composite the active frame with onion-skin ghosts of neighbours.

    Returns the composite as HxWx4 uint8 RGBA, or ``None`` when the
    animation has no frames. ``before_count`` / ``after_count`` control
    how many neighbours on each side appear; ``opacity_step`` is the
    starting opacity of the closest neighbour (the next-closer pair
    gets ``opacity_step * step_factor`` and so on, where ``step_factor``
    defaults to ``opacity_step`` itself — so a step of 0.4 yields
    [0.4, 0.16, 0.064] across three preceding frames).

    Tints are applied to the ghost frames' RGB so the user can tell
    past from future at a glance. The active frame is composited on
    top at full opacity.
    """
    if before_count < 0 or after_count < 0:
        raise ValueError(
            f"before_count / after_count must be >= 0, got "
            f"{before_count} / {after_count}",
        )
    if not 0.0 <= float(opacity_step) <= 1.0:
        raise ValueError(
            f"opacity_step must be in [0, 1], got {opacity_step!r}",
        )
    if not animation.frames:
        return None
    active_frame = animation.active_frame()
    if active_frame is None:
        return None
    shape = active_frame.document.shape
    if shape is None:
        return None
    h, w = shape

    out = np.zeros((h, w, 4), dtype=np.uint8)
    # Active frame at full opacity goes down first so it's the
    # baseline; ghost neighbours overlay on top at reduced opacity.
    out = _composite_active(out, active_frame.document)
    # Before frames — farthest first so the closer (more recent) ones
    # land on top of older ones.
    for distance in range(before_count, 0, -1):
        idx = animation.active_index - distance
        if idx < 0:
            continue
        out = _composite_onion_frame(
            out, animation.frames[idx].document, distance,
            before_tint, opacity_step,
        )
    # After frames — same farthest-first ordering.
    for distance in range(after_count, 0, -1):
        idx = animation.active_index + distance
        if idx >= len(animation.frames):
            continue
        out = _composite_onion_frame(
            out, animation.frames[idx].document, distance,
            after_tint, opacity_step,
        )
    return out


def render_onion_skin_overlay(
    animation: Animation,
    *,
    before_count: int = 1,
    after_count: int = 1,
    before_tint: tuple[int, int, int] = DEFAULT_BEFORE_TINT,
    after_tint: tuple[int, int, int] = DEFAULT_AFTER_TINT,
    opacity_step: float = DEFAULT_OPACITY_STEP,
) -> np.ndarray | None:
    """Render the onion-skin ghosts WITHOUT the active frame.

    Returns an HxWx4 RGBA buffer the canvas can blit as an overlay
    above its own composite. ``None`` is returned when the animation
    has no frames or when neither neighbour direction would produce
    a visible ghost (e.g. ``before_count == 0`` and the active frame
    is the last one).

    Compared with :func:`composite_with_onion_skin` (which produces a
    flattened active+ghosts composite), this overlay-only variant lets
    the user keep editing the active frame's layers normally while
    the canvas widget shows neighbour ghosts on top in a separate pass.
    """
    if before_count < 0 or after_count < 0:
        raise ValueError(
            f"before_count / after_count must be >= 0, got "
            f"{before_count} / {after_count}",
        )
    if not 0.0 <= float(opacity_step) <= 1.0:
        raise ValueError(
            f"opacity_step must be in [0, 1], got {opacity_step!r}",
        )
    if not animation.frames:
        return None
    active_frame = animation.active_frame()
    if active_frame is None:
        return None
    shape = active_frame.document.shape
    if shape is None:
        return None
    h, w = shape

    # Walk both sides farthest-first so closer ghosts overlay older ones.
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for distance in range(before_count, 0, -1):
        idx = animation.active_index - distance
        if idx < 0:
            continue
        out = _composite_onion_frame(
            out, animation.frames[idx].document, distance,
            before_tint, opacity_step,
        )
    for distance in range(after_count, 0, -1):
        idx = animation.active_index + distance
        if idx >= len(animation.frames):
            continue
        out = _composite_onion_frame(
            out, animation.frames[idx].document, distance,
            after_tint, opacity_step,
        )
    if out[..., 3].sum() == 0:
        # No ghost was actually drawn — empty animation edges, all
        # neighbours had alpha-zero composites, etc. Return ``None`` so
        # the canvas can short-circuit the overlay paint.
        return None
    return out


def _composite_active(buffer: np.ndarray, doc: PaintDocument) -> np.ndarray:
    composite = doc.composite()
    if composite is None:
        return buffer
    return composite_layer_pair(buffer, composite)


def _composite_onion_frame(
    buffer: np.ndarray,
    doc: PaintDocument,
    distance: int,
    tint: tuple[int, int, int],
    opacity_step: float,
) -> np.ndarray:
    composite = doc.composite()
    if composite is None or distance < 1:
        return buffer
    # opacity = step ** distance; ensures each successive ghost fades
    # toward the background.
    opacity = float(opacity_step) ** int(distance)
    if opacity <= 0:
        return buffer
    tinted = _tint_rgba(composite, tint, opacity)
    return composite_layer_pair(buffer, tinted, opacity=1.0, blend_mode="normal")


def _tint_rgba(
    image: np.ndarray, tint: tuple[int, int, int], opacity: float,
) -> np.ndarray:
    """Multiply the RGB channels by the tint colour and scale alpha."""
    if image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    tint_arr = np.array(
        [tint[0] / 255.0, tint[1] / 255.0, tint[2] / 255.0],
        dtype=np.float32,
    )
    out = image.copy()
    rgb_f = out[..., :3].astype(np.float32) / 255.0
    rgb_f = rgb_f * tint_arr[None, None, :]
    out[..., :3] = np.clip(rgb_f * 255.0, 0.0, 255.0).astype(np.uint8)
    out[..., 3] = np.clip(
        out[..., 3].astype(np.float32) * float(opacity), 0.0, 255.0,
    ).astype(np.uint8)
    return out
