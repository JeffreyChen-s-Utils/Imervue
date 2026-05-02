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
TAIL_STYLES = ("triangle", "curve", "thought_trail")
DEFAULT_TAIL_STYLE = "triangle"
DEFAULT_BUBBLE_FILL = (255, 255, 255, 255)
DEFAULT_BUBBLE_STROKE = (0, 0, 0, 255)


def render_speech_bubble(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    *,
    style: str = "oval",
    tail_target: tuple[float, float] | None = None,
    tail_style: str = DEFAULT_TAIL_STYLE,
    fill: tuple[int, int, int, int] | None = DEFAULT_BUBBLE_FILL,
    stroke: tuple[int, int, int, int] | None = DEFAULT_BUBBLE_STROKE,
    stroke_width: int = 2,
    corner_radius: int = 12,
    bump_count: int = 12,
    spike_count: int = 12,
) -> DamageRect:
    """Stamp a speech bubble into ``canvas``.

    ``tail_target`` (when given) is the on-canvas point the tail aims
    at; the tail base attaches at the silhouette edge nearest to the
    target so it never floats over a gap between body and tail.
    ``tail_style`` controls the tail shape:

    * ``triangle`` — straight-sided triangle from edge to target
      (default; matches the existing renderer)
    * ``curve``    — three-control-point Bézier-ish curve, gentle
      organic feel to match the bubble outline
    * ``thought_trail`` — sequence of shrinking ellipses (the
      "thought bubble" trail of dots; only meaningful with the
      ``thought`` body style but the rasteriser doesn't enforce it).
    """
    _check_canvas(canvas)
    if style not in BUBBLE_STYLES:
        raise ValueError(
            f"unknown bubble style {style!r}; expected one of {BUBBLE_STYLES}",
        )
    if tail_style not in TAIL_STYLES:
        raise ValueError(
            f"unknown tail style {tail_style!r}; expected one of {TAIL_STYLES}",
        )
    if fill is None and stroke is None:
        return DamageRect(0, 0, 0, 0)
    h, w = canvas.shape[:2]
    body_mask = _bubble_body_mask(
        (h, w), rect, style, corner_radius, bump_count, spike_count,
    )
    if tail_target is not None:
        body_mask = body_mask | _tail_mask(
            (h, w), rect, style, tail_target, tail_style,
            corner_radius=corner_radius,
        )
    if not body_mask.any():
        return DamageRect(0, 0, 0, 0)

    if fill is not None:
        canvas[body_mask] = fill
    if stroke is not None:
        sw = max(1, int(stroke_width))
        inner_rect = _shrink_rect(rect, sw)
        inner = _bubble_body_mask(
            (h, w), inner_rect, style,
            max(0, corner_radius - sw), bump_count, spike_count,
        )
        if tail_target is not None:
            inner = inner | _tail_mask(
                (h, w), inner_rect, style, tail_target, tail_style,
                corner_radius=max(0, corner_radius - sw),
            )
        band = body_mask & ~inner
        if band.any():
            canvas[band] = stroke
    return _damage_from_mask(body_mask)


# ---------------------------------------------------------------------------
# Tail geometry — exposed publicly so a UI preview can draw the tail
# without committing pixels.
# ---------------------------------------------------------------------------


def attachment_point(
    rect: tuple[int, int, int, int],
    style: str,
    target: tuple[float, float],
    *,
    corner_radius: int = 12,
) -> tuple[float, float]:
    """Closest silhouette-edge point along the ray from bubble centre to target.

    For ``oval`` / ``thought`` we project the ray onto the ellipse
    perimeter analytically. For ``rectangular`` we clip the ray to
    the rounded rect's outline. For ``jagged`` we use the bbox edge
    (the silhouette is multi-pointed; landing on an arbitrary spike
    looks worse than landing on the bbox).
    """
    x, y, rw, rh = rect
    cx = float(x) + float(rw) / 2.0
    cy = float(y) + float(rh) / 2.0
    if rw <= 0 or rh <= 0:
        return (cx, cy)
    tx, ty = float(target[0]), float(target[1])
    dx = tx - cx
    dy = ty - cy
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return (cx, cy)
    ux = dx / length
    uy = dy / length
    if style in ("oval", "thought"):
        rx = float(rw) / 2.0
        ry = float(rh) / 2.0
        # Ellipse intersection for the ray (cx + t*ux, cy + t*uy):
        # t² (ux²/rx² + uy²/ry²) = 1 → t = 1 / sqrt(...)
        denom = (ux * ux) / (rx * rx) + (uy * uy) / (ry * ry)
        if denom <= 1e-12:
            return (cx, cy)
        t = 1.0 / math.sqrt(denom)
        return (cx + t * ux, cy + t * uy)
    if style == "rectangular":
        radius = max(0, min(int(corner_radius), rw // 2, rh // 2))
        return _ray_to_rounded_rect((cx, cy), (ux, uy), rect, radius)
    # jagged → bbox edge
    return _ray_to_bbox_edge((cx, cy), (ux, uy), rect)


def compute_tail_polygon(
    rect: tuple[int, int, int, int],
    style: str,
    target: tuple[float, float],
    *,
    tail_style: str = DEFAULT_TAIL_STYLE,
    corner_radius: int = 12,
) -> list[tuple[float, float]]:
    """Return the tail outline as a polygon for preview / hit-testing.

    For ``triangle`` and ``curve`` the result is a closed list of
    points (last point coincides with first). ``thought_trail``
    returns the list of dot centres instead — callers render them as
    a sequence of small ellipses, not a single polygon.
    """
    if tail_style not in TAIL_STYLES:
        raise ValueError(
            f"unknown tail style {tail_style!r}; expected one of {TAIL_STYLES}",
        )
    x, y, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return []
    cx = float(x) + float(rw) / 2.0
    cy = float(y) + float(rh) / 2.0
    tx, ty = float(target[0]), float(target[1])
    if math.hypot(tx - cx, ty - cy) < 1e-6:
        return []
    edge_x, edge_y = attachment_point(
        rect, style, target, corner_radius=corner_radius,
    )
    dx = tx - edge_x
    dy = ty - edge_y
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return []
    ux = dx / length
    uy = dy / length
    perp_x = -uy
    perp_y = ux
    half_width = max(2.0, min(rw, rh) * 0.18)
    base1 = (edge_x + perp_x * half_width, edge_y + perp_y * half_width)
    base2 = (edge_x - perp_x * half_width, edge_y - perp_y * half_width)
    if tail_style == "triangle":
        return [base1, base2, (tx, ty), base1]
    if tail_style == "curve":
        # Thicken near the base, taper toward the tip via two
        # mid-control points so the silhouette reads as a curved
        # triangle instead of a straight one.
        mid1 = (
            edge_x + ux * length * 0.55 + perp_x * half_width * 0.6,
            edge_y + uy * length * 0.55 + perp_y * half_width * 0.6,
        )
        mid2 = (
            edge_x + ux * length * 0.55 - perp_x * half_width * 0.6,
            edge_y + uy * length * 0.55 - perp_y * half_width * 0.6,
        )
        return [base1, mid1, (tx, ty), mid2, base2, base1]
    # thought_trail: dots are CENTRES, not a polygon.
    return _trail_dot_centres((edge_x, edge_y), (tx, ty), half_width)


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
    style: str,
    tail_target: tuple[float, float],
    tail_style: str,
    *,
    corner_radius: int = 12,
) -> np.ndarray:
    h, w = shape
    _, _, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return np.zeros((h, w), dtype=np.bool_)
    poly = compute_tail_polygon(
        rect, style, tail_target,
        tail_style=tail_style, corner_radius=corner_radius,
    )
    if not poly:
        return np.zeros((h, w), dtype=np.bool_)
    if tail_style == "thought_trail":
        return _trail_dot_mask((h, w), poly, rw, rh)
    from Imervue.paint.selection import polygon_mask
    return polygon_mask(h, w, poly)


def _ray_to_rounded_rect(
    origin: tuple[float, float],
    direction: tuple[float, float],
    rect: tuple[int, int, int, int],
    radius: int,
) -> tuple[float, float]:
    """Closed-form ray-rect intersection, with corner rounding handled
    by a final cap inside the shrunk-by-radius inner rectangle."""
    cx, cy = origin
    ux, uy = direction
    x, y, rw, rh = rect
    x0, y0 = float(x), float(y)
    x1, y1 = x0 + float(rw), y0 + float(rh)
    # Clip to each axis-aligned slab; smallest positive t wins.
    candidates: list[float] = []
    if abs(ux) > 1e-9:
        candidates.append(((x0 if ux < 0 else x1) - cx) / ux)
    if abs(uy) > 1e-9:
        candidates.append(((y0 if uy < 0 else y1) - cy) / uy)
    positives = [t for t in candidates if t > 0]
    if not positives:
        return (cx, cy)
    t = min(positives)
    foot_x = cx + t * ux
    foot_y = cy + t * uy
    # Pull inwards a radius-worth so the tail sits inside the rounded
    # corner curvature instead of past it on the corner-truncated edge.
    if radius > 0:
        foot_x -= ux * float(radius) * 0.4
        foot_y -= uy * float(radius) * 0.4
    return (foot_x, foot_y)


def _ray_to_bbox_edge(
    origin: tuple[float, float],
    direction: tuple[float, float],
    rect: tuple[int, int, int, int],
) -> tuple[float, float]:
    cx, cy = origin
    ux, uy = direction
    _, _, rw, rh = rect
    half_w = float(rw) / 2.0
    half_h = float(rh) / 2.0
    # Scale so |ux*t| ≤ half_w AND |uy*t| ≤ half_h — t = min of the
    # two axis-clip distances.
    tx = half_w / abs(ux) if abs(ux) > 1e-9 else math.inf
    ty = half_h / abs(uy) if abs(uy) > 1e-9 else math.inf
    t = min(tx, ty)
    return (cx + t * ux, cy + t * uy)


def _trail_dot_centres(
    base: tuple[float, float],
    target: tuple[float, float],
    half_width: float,
) -> list[tuple[float, float]]:
    """Generate centre points for the thought-bubble dot trail.

    Three dots, decreasing in radius along the way to the target —
    the largest sits closest to the bubble, the smallest at the tip.
    Returns the centres only; the rasteriser draws ellipses around
    them with the matching radii.
    """
    bx, by = base
    tx, ty = target
    out: list[tuple[float, float]] = []
    for ratio in (0.25, 0.55, 0.9):
        cx = bx + (tx - bx) * ratio
        cy = by + (ty - by) * ratio
        out.append((cx, cy))
    # Stash half_width on the list via a sentinel so the rasteriser
    # knows the size scale without re-deriving it. Tuple-of-tuples is
    # cleaner — return centre + radius pairs disguised as 2-tuples by
    # encoding radius into the offset would be confusing. Keep it
    # simple: just centres; radius is min(half_width, 6/4/2).
    return out


def _trail_dot_mask(
    shape: tuple[int, int],
    centres: list[tuple[float, float]],
    rw: int, rh: int,
) -> np.ndarray:
    h, w = shape
    out = np.zeros((h, w), dtype=np.bool_)
    if not centres:
        return out
    base_radius = max(2.0, min(rw, rh) * 0.10)
    ys, xs = np.indices((h, w), dtype=np.float32)
    for i, (cx, cy) in enumerate(centres):
        # Shrink each successive dot by 30% so the trail tapers.
        radius = base_radius * (0.7 ** i)
        out |= ((xs - cx) ** 2 + (ys - cy) ** 2) <= radius * radius
    return out


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
