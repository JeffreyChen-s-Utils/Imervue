"""Damage-rectangle bookkeeping for partial texture uploads.

A :class:`DamageRect` is the bounding box of modified pixels on the
canvas. The brush engine reports rects as it stamps dabs; the canvas
unions them across the stroke and uploads only the touched region to
the GPU instead of the whole 4 MB texture.

Pure-math, Qt-free. The integration with the GL canvas lives in
:mod:`Imervue.paint.canvas`; the integration with the brush lives in
:mod:`Imervue.paint.tool_dispatcher`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DamageRect:
    """Axis-aligned rectangle in image-space pixels.

    ``x`` / ``y`` are the top-left corner; ``w`` / ``h`` are positive
    extents. An "empty" rect (``w <= 0`` or ``h <= 0``) is the
    additive-identity for :meth:`union`.
    """

    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

    @property
    def is_empty(self) -> bool:
        return self.w <= 0 or self.h <= 0

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    def union(self, other: DamageRect) -> DamageRect:
        """Smallest rect containing both self and other.

        Empty rects are absorbed by the non-empty side; two empty
        rects union to an empty rect.
        """
        if self.is_empty:
            return other
        if other.is_empty:
            return self
        x0 = min(self.x, other.x)
        y0 = min(self.y, other.y)
        x1 = max(self.x2, other.x2)
        y1 = max(self.y2, other.y2)
        return DamageRect(x=x0, y=y0, w=x1 - x0, h=y1 - y0)

    def inflate(self, margin: int) -> DamageRect:
        """Grow each side by ``margin`` pixels (negative shrinks).

        Empty rects pass through unchanged so a no-op damage doesn't
        spawn a non-empty inflated phantom.
        """
        if self.is_empty:
            return self
        return DamageRect(
            x=self.x - int(margin),
            y=self.y - int(margin),
            w=self.w + 2 * int(margin),
            h=self.h + 2 * int(margin),
        )

    def clipped_to(self, shape: tuple[int, int]) -> DamageRect:
        """Clip the rect to ``(height, width)`` canvas bounds.

        Off-canvas damage is normal at the edges of strokes; this
        gives back the in-bounds slice so the GPU upload doesn't fail
        with a "rectangle exceeds texture size" error. Yields an
        empty rect when the damage is fully off-canvas.
        """
        if self.is_empty:
            return self
        h, w = shape
        x0 = max(0, self.x)
        y0 = max(0, self.y)
        x1 = min(int(w), self.x2)
        y1 = min(int(h), self.y2)
        if x1 <= x0 or y1 <= y0:
            return DamageRect()
        return DamageRect(x=x0, y=y0, w=x1 - x0, h=y1 - y0)

    def covers_full(self, shape: tuple[int, int]) -> bool:
        """Return True if this rect is at least as large as ``shape``.

        The canvas uses this to decide between a full-frame upload
        (``glTexImage2D``) and a sub-region upload
        (``glTexSubImage2D``) — once the damage covers the entire
        canvas the partial path saves nothing.
        """
        if self.is_empty:
            return False
        h, w = shape
        return (
            self.x <= 0
            and self.y <= 0
            and self.x2 >= int(w)
            and self.y2 >= int(h)
        )


# Module-level singleton so callers that want to "no-op" don't have to
# re-instantiate. Frozen, so safe to share.
EMPTY = DamageRect()


def from_dab_result(result) -> DamageRect:
    """Convert a :class:`Imervue.paint.brush_engine.DabResult` to a
    :class:`DamageRect`. Both share the same field shape so this is
    just a constructor — but keeping it as an explicit helper lets
    the caller stay decoupled from the brush engine module."""
    return DamageRect(x=int(result.x), y=int(result.y), w=int(result.w), h=int(result.h))

Rect = tuple[int, int, int, int]


def union_rects(a: Rect, b: Rect) -> Rect:
    """Union two ``(x, y, w, h)`` tuples; an empty one returns the other.

    Tuple form of :meth:`DamageRect.union`, used by the tools that accumulate
    a stroke's damage before converting it once.
    """
    if a[2] <= 0 or a[3] <= 0:
        return b
    if b[2] <= 0 or b[3] <= 0:
        return a
    x0 = min(a[0], b[0])
    y0 = min(a[1], b[1])
    x1 = max(a[0] + a[2], b[0] + b[2])
    y1 = max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)


def from_rect(rect: Rect) -> DamageRect:
    """Convert an ``(x, y, w, h)`` tuple to a :class:`DamageRect`.

    An empty tuple (non-positive extent) yields the shared :data:`EMPTY`.
    """
    if rect[2] <= 0 or rect[3] <= 0:
        return EMPTY
    return DamageRect(x=rect[0], y=rect[1], w=rect[2], h=rect[3])
