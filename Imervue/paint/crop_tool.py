"""Crop-tool helpers — aspect-ratio snapping + commit hand-off.

The dispatcher tool itself lives in :mod:`Imervue.paint.tool_dispatcher`;
this module owns the pure logic so it can be unit-tested without a
canvas / Qt event loop.

Aspect ratios are expressed as ``(w_units, h_units)`` tuples — e.g.
``(16, 9)`` for widescreen, ``(1, 1)`` for square. ``None`` means
"freeform" — the user's drag rect is committed unchanged.
"""
from __future__ import annotations

# Built-in aspect-ratio presets. The dropdown order matches MediBang
# (widest first, then square, then portrait). ``None`` is the
# "Freeform" entry.
ASPECT_PRESETS: tuple[tuple[str, tuple[int, int] | None], ...] = (
    ("Freeform", None),
    ("1:1", (1, 1)),
    ("3:2", (3, 2)),
    ("4:3", (4, 3)),
    ("16:9", (16, 9)),
    ("2:3", (2, 3)),
    ("3:4", (3, 4)),
    ("9:16", (9, 16)),
)
DEFAULT_ASPECT: tuple[int, int] | None = None


def snap_to_aspect(
    x0: float, y0: float, x1: float, y1: float,
    aspect: tuple[int, int] | None,
) -> tuple[float, float, float, float]:
    """Adjust ``(x1, y1)`` so the rect from ``(x0, y0)`` matches ``aspect``.

    The drag's *anchor* corner stays put; the dragged corner moves so
    the resulting width / height ratio equals ``aspect``. The rect
    grows to whichever dimension the user dragged further — so a
    short-and-wide drag with aspect ``1:1`` becomes a square sized
    by the wider axis.

    ``aspect=None`` returns the rect unchanged. Passing a degenerate
    ``aspect`` (zero or negative component) raises ``ValueError``
    rather than silently dividing by zero.
    """
    if aspect is None:
        return (float(x0), float(y0), float(x1), float(y1))
    aw, ah = aspect
    if aw <= 0 or ah <= 0:
        raise ValueError(
            f"aspect components must be positive, got {aspect!r}",
        )
    dx = float(x1) - float(x0)
    dy = float(y1) - float(y0)
    if dx == 0 and dy == 0:
        return (float(x0), float(y0), float(x1), float(y1))
    ratio = float(aw) / float(ah)
    abs_dx = abs(dx)
    abs_dy = abs(dy)
    if abs_dx / ratio >= abs_dy:
        # Width is the dominant axis — derive height from it.
        new_dy = (abs_dx / ratio) * (1 if dy >= 0 else -1)
        return (float(x0), float(y0), float(x0) + dx, float(y0) + new_dy)
    new_dx = (abs_dy * ratio) * (1 if dx >= 0 else -1)
    return (float(x0), float(y0), float(x0) + new_dx, float(y0) + dy)


def normalise_rect(
    x0: float, y0: float, x1: float, y1: float,
    canvas_shape: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    """Convert two corners into a positive integer (x, y, w, h)
    clipped to ``canvas_shape``.

    Returns ``None`` for a zero-area rect so the caller can skip the
    commit instead of cropping the canvas to nothing.
    """
    h_canvas, w_canvas = canvas_shape
    rx = int(round(min(x0, x1)))
    ry = int(round(min(y0, y1)))
    rw = int(round(abs(x1 - x0)))
    rh = int(round(abs(y1 - y0)))
    if rw <= 0 or rh <= 0:
        return None
    rx_c = max(0, rx)
    ry_c = max(0, ry)
    rw_c = max(0, min(rx + rw, w_canvas) - rx_c)
    rh_c = max(0, min(ry + rh, h_canvas) - ry_c)
    if rw_c <= 0 or rh_c <= 0:
        return None
    return (rx_c, ry_c, rw_c, rh_c)
