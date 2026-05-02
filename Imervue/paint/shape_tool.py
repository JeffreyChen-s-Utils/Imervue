"""Pure-numpy shape primitives for the Paint workspace.

Four geometric shapes that rasterise into an HxWx4 RGBA buffer with
optional fill colour, optional stroke (outline) colour, and stroke
width:

* :func:`render_rectangle` — axis-aligned rectangle from a
  ``(x, y, w, h)`` rect.
* :func:`render_ellipse` — axis-aligned ellipse inscribed in a rect.
* :func:`render_regular_polygon` — regular N-sided polygon centred
  at a point with a circumscribed radius and an optional rotation.
* :func:`render_star` — N-pointed star with separate inner / outer
  radii (defaults to 5-point with ``inner = 0.5 * outer``).

Each helper mutates ``canvas`` in place and returns a
:class:`Imervue.paint.manga_effects.DamageRect` so the canvas widget
can schedule a partial repaint instead of a full upload. Stroke is
implemented as the band between the outer mask and an inner mask
shrunk by ``stroke_width``; that yields crisp strokes for rectangles
+ axis-aligned ellipses and a respectable approximation for
polygons / stars (the inner shape is scaled radially toward the
centre, which preserves the corner geometry without an extra
distance-transform pass).

Pure numpy / Qt-free so a fill-bucket-or-shape decision in the
dispatcher pays no Qt import cost.
"""
from __future__ import annotations

import math

import numpy as np

from Imervue.paint.manga_effects import DamageRect

# Stroke band is at least 1 px to avoid a "stroke=None" appearing
# when the user types ``stroke_width=0`` then expects an outline.
MIN_STROKE_WIDTH = 1


def render_rectangle(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int, int] | None = None,
    stroke: tuple[int, int, int, int] | None = None,
    stroke_width: int = 1,
) -> DamageRect:
    """Stamp an axis-aligned rectangle into ``canvas``."""
    _check_canvas(canvas)
    if fill is None and stroke is None:
        return DamageRect(0, 0, 0, 0)
    h, w = canvas.shape[:2]
    outer = _rect_mask((h, w), rect)
    if not outer.any():
        return DamageRect(0, 0, 0, 0)
    if fill is not None:
        canvas[outer] = fill
    if stroke is not None:
        sw = max(MIN_STROKE_WIDTH, int(stroke_width))
        x, y, rw, rh = rect
        inner_rect = (
            x + sw, y + sw,
            max(0, rw - 2 * sw), max(0, rh - 2 * sw),
        )
        inner = _rect_mask((h, w), inner_rect)
        band = outer & ~inner
        if band.any():
            canvas[band] = stroke
    return _damage_from_mask(outer)


def render_ellipse(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int, int] | None = None,
    stroke: tuple[int, int, int, int] | None = None,
    stroke_width: int = 1,
) -> DamageRect:
    """Stamp an axis-aligned ellipse inscribed in ``rect``."""
    _check_canvas(canvas)
    if fill is None and stroke is None:
        return DamageRect(0, 0, 0, 0)
    h, w = canvas.shape[:2]
    outer = _ellipse_mask((h, w), rect)
    if not outer.any():
        return DamageRect(0, 0, 0, 0)
    if fill is not None:
        canvas[outer] = fill
    if stroke is not None:
        sw = max(MIN_STROKE_WIDTH, int(stroke_width))
        x, y, rw, rh = rect
        inner_rect = (
            x + sw, y + sw,
            max(0, rw - 2 * sw), max(0, rh - 2 * sw),
        )
        inner = _ellipse_mask((h, w), inner_rect)
        band = outer & ~inner
        if band.any():
            canvas[band] = stroke
    return _damage_from_mask(outer)


def render_regular_polygon(
    canvas: np.ndarray,
    center: tuple[float, float],
    radius: float,
    n_sides: int,
    *,
    fill: tuple[int, int, int, int] | None = None,
    stroke: tuple[int, int, int, int] | None = None,
    stroke_width: int = 1,
    rotation_deg: float = 0.0,
) -> DamageRect:
    """Stamp a regular N-sided polygon centred at ``center``.

    ``radius`` is the circumscribed circle radius (distance from
    centre to vertex). ``rotation_deg = 0`` puts the first vertex
    pointing right (+x); positive rotation is counter-clockwise.
    """
    _check_canvas(canvas)
    if n_sides < 3:
        raise ValueError(f"n_sides must be >= 3, got {n_sides}")
    if radius <= 0:
        raise ValueError(f"radius must be > 0, got {radius}")
    if fill is None and stroke is None:
        return DamageRect(0, 0, 0, 0)
    h, w = canvas.shape[:2]
    outer_pts = _regular_polygon_vertices(center, radius, n_sides, rotation_deg)
    outer = _polygon_mask((h, w), outer_pts)
    if not outer.any():
        return DamageRect(0, 0, 0, 0)
    if fill is not None:
        canvas[outer] = fill
    if stroke is not None:
        sw = max(MIN_STROKE_WIDTH, int(stroke_width))
        inner_radius = max(0.0, float(radius) - float(sw))
        if inner_radius > 0:
            inner_pts = _regular_polygon_vertices(
                center, inner_radius, n_sides, rotation_deg,
            )
            inner = _polygon_mask((h, w), inner_pts)
            band = outer & ~inner
        else:
            band = outer
        if band.any():
            canvas[band] = stroke
    return _damage_from_mask(outer)


def render_star(
    canvas: np.ndarray,
    center: tuple[float, float],
    outer_radius: float,
    n_points: int,
    *,
    inner_radius: float | None = None,
    fill: tuple[int, int, int, int] | None = None,
    stroke: tuple[int, int, int, int] | None = None,
    stroke_width: int = 1,
    rotation_deg: float = -90.0,
) -> DamageRect:
    """Stamp an N-pointed star centred at ``center``.

    ``outer_radius`` is the distance from the centre to a tip;
    ``inner_radius`` is the distance to the valleys between tips.
    Defaults to ``0.5 * outer_radius``, which is the proportion that
    matches a classic 5-point star. ``rotation_deg = -90`` puts the
    first tip at the top (the natural orientation a user expects).
    """
    _check_canvas(canvas)
    if n_points < 3:
        raise ValueError(f"n_points must be >= 3, got {n_points}")
    if outer_radius <= 0:
        raise ValueError(f"outer_radius must be > 0, got {outer_radius}")
    if inner_radius is None:
        inner_radius = float(outer_radius) * 0.5
    if not 0 < inner_radius < outer_radius:
        raise ValueError(
            f"inner_radius must satisfy 0 < inner < outer, "
            f"got {inner_radius!r} vs outer={outer_radius!r}",
        )
    if fill is None and stroke is None:
        return DamageRect(0, 0, 0, 0)
    h, w = canvas.shape[:2]
    outer_pts = _star_vertices(
        center, outer_radius, inner_radius, n_points, rotation_deg,
    )
    outer = _polygon_mask((h, w), outer_pts)
    if not outer.any():
        return DamageRect(0, 0, 0, 0)
    if fill is not None:
        canvas[outer] = fill
    if stroke is not None:
        sw = max(MIN_STROKE_WIDTH, int(stroke_width))
        scale = max(0.0, 1.0 - float(sw) / float(outer_radius))
        if scale > 0:
            inner_outer = float(outer_radius) * scale
            inner_inner = float(inner_radius) * scale
            inner_pts = _star_vertices(
                center, inner_outer, inner_inner, n_points, rotation_deg,
            )
            inner = _polygon_mask((h, w), inner_pts)
            band = outer & ~inner
        else:
            band = outer
        if band.any():
            canvas[band] = stroke
    return _damage_from_mask(outer)


# ---------------------------------------------------------------------------
# Mask builders
# ---------------------------------------------------------------------------


def _rect_mask(shape: tuple[int, int], rect: tuple[int, int, int, int]) -> np.ndarray:
    h, w = shape
    x, y, rw, rh = rect
    mask = np.zeros((h, w), dtype=np.bool_)
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(w, int(x) + int(rw))
    y1 = min(h, int(y) + int(rh))
    if x1 > x0 and y1 > y0:
        mask[y0:y1, x0:x1] = True
    return mask


def _ellipse_mask(shape: tuple[int, int], rect: tuple[int, int, int, int]) -> np.ndarray:
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


def _polygon_mask(shape: tuple[int, int], points: list[tuple[float, float]]) -> np.ndarray:
    """Re-export the marquee polygon rasteriser to keep all shape masks
    flowing through one tested code path."""
    from Imervue.paint.selection import polygon_mask
    return polygon_mask(shape[0], shape[1], points)


# ---------------------------------------------------------------------------
# Vertex generators
# ---------------------------------------------------------------------------


def _regular_polygon_vertices(
    center: tuple[float, float], radius: float, n_sides: int, rotation_deg: float,
) -> list[tuple[float, float]]:
    cx, cy = float(center[0]), float(center[1])
    rad0 = math.radians(rotation_deg)
    step = 2.0 * math.pi / n_sides
    return [
        (cx + radius * math.cos(rad0 + i * step),
         cy + radius * math.sin(rad0 + i * step))
        for i in range(n_sides)
    ]


def _star_vertices(
    center: tuple[float, float],
    outer_radius: float,
    inner_radius: float,
    n_points: int,
    rotation_deg: float,
) -> list[tuple[float, float]]:
    cx, cy = float(center[0]), float(center[1])
    rad0 = math.radians(rotation_deg)
    step = math.pi / n_points     # half-step between tip and valley
    out: list[tuple[float, float]] = []
    for i in range(2 * n_points):
        r = outer_radius if i % 2 == 0 else inner_radius
        angle = rad0 + i * step
        out.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return out


# ---------------------------------------------------------------------------
# Damage helpers + canvas check
# ---------------------------------------------------------------------------


def _damage_from_mask(mask: np.ndarray) -> DamageRect:
    if not mask.any():
        return DamageRect(0, 0, 0, 0)
    ys, xs = np.nonzero(mask)
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
