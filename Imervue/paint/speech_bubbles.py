"""Speech-bubble rasteriser for the manga workflow.

Four bubble silhouettes plus an optional tail that points to a
caller-supplied target — completes the manga toolset that 5c left
without dialog support.

Styles:

* ``oval``        — rounded ellipse, the default speech bubble
* ``rectangular`` — rounded-corner rectangle, more formal /
                    expository tone
* ``thought``     — cloud silhouette: an ellipse fringed with N
                    small bumps along the perimeter
* ``jagged``      — N-spike starburst, the "shouting / impact"
                    bubble used for sound effects

Each bubble accepts a ``tail_target`` point — a triangle is drawn
from the bubble's centre toward the target, tapering to a sharp
tip. The tail is unioned into the bubble's mask before fill /
stroke are applied so the tail edges read as one continuous
silhouette rather than a separate sticker.

Pure numpy / Qt-free; mutates an HxWx4 RGBA buffer in place and
returns a :class:`DamageRect` for partial repaints.
"""
from __future__ import annotations

import math

import numpy as np

from Imervue.paint.manga_effects import DamageRect

BUBBLE_STYLES = ("oval", "rectangular", "thought", "jagged")
DEFAULT_BUBBLE_FILL = (255, 255, 255, 255)
DEFAULT_BUBBLE_STROKE = (0, 0, 0, 255)


def render_speech_bubble(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    *,
    style: str = "oval",
    tail_target: tuple[float, float] | None = None,
    fill: tuple[int, int, int, int] | None = DEFAULT_BUBBLE_FILL,
    stroke: tuple[int, int, int, int] | None = DEFAULT_BUBBLE_STROKE,
    stroke_width: int = 2,
    corner_radius: int = 12,
    bump_count: int = 12,
    spike_count: int = 12,
) -> DamageRect:
    """Stamp a speech bubble into ``canvas``."""
    _check_canvas(canvas)
    if style not in BUBBLE_STYLES:
        raise ValueError(
            f"unknown bubble style {style!r}; expected one of {BUBBLE_STYLES}",
        )
    if fill is None and stroke is None:
        return DamageRect(0, 0, 0, 0)
    h, w = canvas.shape[:2]
    body_mask = _bubble_body_mask(
        (h, w), rect, style, corner_radius, bump_count, spike_count,
    )
    if tail_target is not None:
        body_mask = body_mask | _tail_mask((h, w), rect, tail_target)
    if not body_mask.any():
        return DamageRect(0, 0, 0, 0)

    if fill is not None:
        canvas[body_mask] = fill
    if stroke is not None:
        sw = max(1, int(stroke_width))
        inner = _bubble_body_mask(
            (h, w), _shrink_rect(rect, sw), style,
            max(0, corner_radius - sw), bump_count, spike_count,
        )
        if tail_target is not None:
            inner = inner | _tail_mask((h, w), _shrink_rect(rect, sw), tail_target)
        band = body_mask & ~inner
        if band.any():
            canvas[band] = stroke
    return _damage_from_mask(body_mask)


# ---------------------------------------------------------------------------
# Body mask builders per style
# ---------------------------------------------------------------------------


def _bubble_body_mask(
    shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    style: str,
    corner_radius: int,
    bump_count: int,
    spike_count: int,
) -> np.ndarray:
    if style == "oval":
        return _ellipse_mask(shape, rect)
    if style == "rectangular":
        return _rounded_rect_mask(shape, rect, corner_radius)
    if style == "thought":
        return _thought_mask(shape, rect, bump_count)
    return _jagged_mask(shape, rect, spike_count)


def _ellipse_mask(
    shape: tuple[int, int], rect: tuple[int, int, int, int],
) -> np.ndarray:
    h, w = shape
    x, y, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return np.zeros((h, w), dtype=np.bool_)
    cx = float(x) + float(rw) / 2.0 - 0.5
    cy = float(y) + float(rh) / 2.0 - 0.5
    rx = float(rw) / 2.0
    ry = float(rh) / 2.0
    ys, xs = np.indices((h, w), dtype=np.float32)
    nx = (xs - cx) / max(rx, 1e-6)
    ny = (ys - cy) / max(ry, 1e-6)
    return (nx * nx + ny * ny) <= 1.0


def _rounded_rect_mask(
    shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    radius: int,
) -> np.ndarray:
    h, w = shape
    x, y, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return np.zeros((h, w), dtype=np.bool_)
    radius = max(0, min(int(radius), rw // 2, rh // 2))
    x0, y0 = float(x), float(y)
    x1, y1 = float(x + rw), float(y + rh)
    ys, xs = np.indices((h, w), dtype=np.float32)
    in_bounds = (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)
    if radius == 0:
        return in_bounds
    nx = np.clip(xs, x0 + radius, x1 - radius - 1)
    ny = np.clip(ys, y0 + radius, y1 - radius - 1)
    dx = xs - nx
    dy = ys - ny
    return in_bounds & ((dx * dx + dy * dy) <= radius * radius)


def _thought_mask(
    shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    bump_count: int,
) -> np.ndarray:
    base = _ellipse_mask(shape, rect)
    if bump_count <= 0:
        return base
    h, w = shape
    x, y, rw, rh = rect
    cx = float(x) + float(rw) / 2.0
    cy = float(y) + float(rh) / 2.0
    rx = float(rw) / 2.0
    ry = float(rh) / 2.0
    bump_radius = max(2.0, min(rw, rh) * 0.08)
    ys, xs = np.indices((h, w), dtype=np.float32)
    out = base.copy()
    for i in range(bump_count):
        angle = 2.0 * math.pi * i / bump_count
        bx = cx + rx * math.cos(angle)
        by = cy + ry * math.sin(angle)
        out |= ((xs - bx) ** 2 + (ys - by) ** 2) <= bump_radius * bump_radius
    return out


def _jagged_mask(
    shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    spike_count: int,
) -> np.ndarray:
    """Starburst silhouette — alternating tips and valleys around the
    bbox centre."""
    from Imervue.paint.shape_tool import _star_vertices, _polygon_mask
    h, w = shape
    x, y, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return np.zeros((h, w), dtype=np.bool_)
    cx = float(x) + float(rw) / 2.0
    cy = float(y) + float(rh) / 2.0
    outer = min(rw, rh) / 2.0
    inner = outer * 0.7   # shallow valleys → "shouting" silhouette
    n_points = max(3, int(spike_count))
    pts = _star_vertices((cx, cy), outer, inner, n_points, rotation_deg=-90.0)
    return _polygon_mask((h, w), pts)


# ---------------------------------------------------------------------------
# Tail
# ---------------------------------------------------------------------------


def _tail_mask(
    shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    tail_target: tuple[float, float],
) -> np.ndarray:
    h, w = shape
    x, y, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return np.zeros((h, w), dtype=np.bool_)
    cx = float(x) + float(rw) / 2.0
    cy = float(y) + float(rh) / 2.0
    tx, ty = float(tail_target[0]), float(tail_target[1])
    dx = tx - cx
    dy = ty - cy
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return np.zeros((h, w), dtype=np.bool_)
    ux = dx / length
    uy = dy / length
    perp_x = -uy
    perp_y = ux
    half_width = max(2.0, min(rw, rh) * 0.18)
    edge_x = cx + ux * (rw / 2.0)
    edge_y = cy + uy * (rh / 2.0)
    base1 = (edge_x + perp_x * half_width, edge_y + perp_y * half_width)
    base2 = (edge_x - perp_x * half_width, edge_y - perp_y * half_width)
    from Imervue.paint.selection import polygon_mask
    return polygon_mask(h, w, [base1, base2, (tx, ty)])


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def _shrink_rect(
    rect: tuple[int, int, int, int], n: int,
) -> tuple[int, int, int, int]:
    x, y, rw, rh = rect
    return (x + n, y + n, max(0, rw - 2 * n), max(0, rh - 2 * n))


def _damage_from_mask(mask: np.ndarray) -> DamageRect:
    if not mask.any():
        return DamageRect(0, 0, 0, 0)
    ys, xs = np.where(mask)
    return DamageRect(
        x=int(xs.min()),
        y=int(ys.min()),
        w=int(xs.max() - xs.min() + 1),
        h=int(ys.max() - ys.min() + 1),
    )


def _check_canvas(canvas: np.ndarray) -> None:
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
