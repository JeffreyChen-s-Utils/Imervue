"""Manga speed lines + halftone screentone helpers.

Two pure-numpy effects that mutate an HxWx4 RGBA uint8 canvas in
place and return a damage rectangle so the caller can schedule a
partial repaint:

* :func:`render_speed_lines` — radial ink lines fanning out from a
  focal point. Used to imply motion or focus inside a panel. The
  lines run from ``inner_radius`` to ``outer_radius`` (so the focal
  region stays clear) over the angular sweep
  ``[angle_start_deg, angle_end_deg]``. ``length_jitter`` perturbs
  the outer endpoint per-line so the fan reads as hand-drawn rather
  than mechanically uniform.
* :func:`render_halftone` — a regular grid of ink dots (or a single
  dot if the spacing is set high) that fills a selection mask.
  Used to fake the printer-screentone shading of traditional manga.

Qt-free; tests can run without a display server.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

DEFAULT_SPEED_LINE_COLOR = (0, 0, 0)
DEFAULT_HALFTONE_COLOR = (0, 0, 0)
SPEED_LINE_MIN_RADIUS = 0.0


@dataclass(frozen=True)
class DamageRect:
    """Bounding box of pixels that changed."""

    x: int
    y: int
    w: int
    h: int

    @property
    def is_empty(self) -> bool:
        return self.w <= 0 or self.h <= 0


# ---------------------------------------------------------------------------
# Speed lines
# ---------------------------------------------------------------------------


def render_speed_lines(
    canvas: np.ndarray,
    centre: tuple[float, float],
    *,
    count: int = 32,
    inner_radius: float = 30.0,
    outer_radius: float = 200.0,
    angle_start_deg: float = 0.0,
    angle_end_deg: float = 360.0,
    line_width: int = 1,
    color: tuple[int, int, int] = DEFAULT_SPEED_LINE_COLOR,
    length_jitter: float = 0.0,
    seed: int = 0,
) -> DamageRect:
    """Stamp ``count`` radial lines from ``centre`` into ``canvas``.

    The lines are evenly distributed in angle across the requested
    sweep. ``length_jitter`` in ``[0, 1]`` scales the outer endpoint
    by ``1 - rng.uniform(0, length_jitter)`` per line so the fan
    looks hand-drawn rather than perfectly mechanical.
    """
    _check_canvas(canvas)
    if count <= 0:
        return DamageRect(0, 0, 0, 0)
    if inner_radius < SPEED_LINE_MIN_RADIUS or outer_radius <= inner_radius:
        raise ValueError(
            f"radii must satisfy 0 <= inner < outer, got "
            f"inner={inner_radius!r} outer={outer_radius!r}",
        )
    if line_width <= 0:
        raise ValueError(f"line_width must be >= 1, got {line_width}")
    if not 0.0 <= length_jitter <= 1.0:
        raise ValueError(
            f"length_jitter must be in [0, 1], got {length_jitter}",
        )

    rng = np.random.default_rng(seed)
    cx, cy = float(centre[0]), float(centre[1])
    sweep = math.radians(angle_end_deg - angle_start_deg)
    start = math.radians(angle_start_deg)
    # When the sweep is a full circle we want N lines without doubling
    # up at the seam; for a partial sweep we pin the first and last
    # endpoints by including both ends.
    is_full_circle = abs(sweep - 2.0 * math.pi) < 1e-9
    if count == 1:
        angles = np.array([start], dtype=np.float64)
    elif is_full_circle:
        angles = start + np.arange(count, dtype=np.float64) * (sweep / count)
    else:
        angles = start + np.linspace(0.0, 1.0, count) * sweep

    fill = (color[0], color[1], color[2], 255)
    accum = _EmptyDamage()
    for angle in angles:
        scale = 1.0 - float(rng.uniform(0.0, length_jitter)) if length_jitter > 0 else 1.0
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        x0 = cx + inner_radius * cos_a
        y0 = cy + inner_radius * sin_a
        end = inner_radius + (outer_radius - inner_radius) * scale
        x1 = cx + end * cos_a
        y1 = cy + end * sin_a
        rect = _draw_thick_line(canvas, x0, y0, x1, y1, line_width, fill)
        accum.merge(rect)
    return accum.to_rect()


# ---------------------------------------------------------------------------
# Halftone
# ---------------------------------------------------------------------------


def render_tonal_halftone(
    canvas: np.ndarray,
    source: np.ndarray,
    *,
    dot_max_radius: float = 4.0,
    spacing: float = 8.0,
    color: tuple[int, int, int] = DEFAULT_HALFTONE_COLOR,
    invert: bool = False,
) -> DamageRect:
    """Variable-density halftone — dot radius scales by source luminance.

    Classic comic-shading effect: every grid-cell centre samples the
    luminance of the source image at that point and stamps a dot
    whose radius is proportional to ``(1 - luminance)`` (so darker
    source pixels → bigger dots, lighter → smaller / none). With
    ``invert=True`` the relationship reverses, useful for "fill the
    bright areas with a stipple texture".

    ``source`` must be the same HxW shape as ``canvas``; the alpha
    channel of the source is ignored — only RGB luminance matters.
    """
    _check_canvas(canvas)
    _check_canvas(source)
    h, w = canvas.shape[:2]
    if source.shape[:2] != (h, w):
        raise ValueError(
            f"source shape {source.shape[:2]} does not match canvas {(h, w)}",
        )
    if spacing <= 0.0:
        raise ValueError(f"spacing must be > 0, got {spacing}")
    if dot_max_radius < 0.0:
        raise ValueError(f"dot_max_radius must be >= 0, got {dot_max_radius}")

    src_rgb = source[..., :3].astype(np.float32)
    luminance = (
        0.299 * src_rgb[..., 0]
        + 0.587 * src_rgb[..., 1]
        + 0.114 * src_rgb[..., 2]
    ) / 255.0

    ys, xs = np.indices((h, w), dtype=np.float32)
    grid_x = np.round(xs / spacing) * spacing
    grid_y = np.round(ys / spacing) * spacing
    fx = xs - grid_x
    fy = ys - grid_y
    distance_to_centre_sq = fx * fx + fy * fy

    centre_xi = np.clip(grid_x.astype(np.int32), 0, w - 1)
    centre_yi = np.clip(grid_y.astype(np.int32), 0, h - 1)
    centre_lum = luminance[centre_yi, centre_xi]
    if invert:
        local_radius = float(dot_max_radius) * centre_lum
    else:
        local_radius = float(dot_max_radius) * (1.0 - centre_lum)

    # Strict positive radius guard — at zero radius the equality test
    # ``distance_sq <= 0`` would still light up every grid centre pixel.
    inside = (
        (local_radius > 0.0)
        & (distance_to_centre_sq <= local_radius * local_radius)
    )
    if not inside.any():
        return DamageRect(0, 0, 0, 0)

    canvas[inside] = (color[0], color[1], color[2], 255)
    ys_hit, xs_hit = np.where(inside)
    return DamageRect(
        x=int(xs_hit.min()),
        y=int(ys_hit.min()),
        w=int(xs_hit.max() - xs_hit.min() + 1),
        h=int(ys_hit.max() - ys_hit.min() + 1),
    )


def render_halftone(
    canvas: np.ndarray,
    selection: np.ndarray | None = None,
    *,
    dot_radius: float = 3.0,
    spacing: float = 8.0,
    angle_deg: float = 0.0,
    color: tuple[int, int, int] = DEFAULT_HALFTONE_COLOR,
) -> DamageRect:
    """Fill the canvas (or ``selection`` mask) with a halftone dot grid.

    Dots of radius ``dot_radius`` are tiled at distance ``spacing``
    apart on a square grid rotated by ``angle_deg`` around the canvas
    origin. ``dot_radius >= spacing/sqrt(2)`` produces overlapping
    dots that fully cover the region — at that point the result is a
    flat fill and the caller probably wants ``flood_fill`` instead.
    """
    _check_canvas(canvas)
    if spacing <= 0.0:
        raise ValueError(f"spacing must be > 0, got {spacing}")
    if dot_radius < 0.0:
        raise ValueError(f"dot_radius must be >= 0, got {dot_radius}")
    if dot_radius == 0.0:
        return DamageRect(0, 0, 0, 0)
    h, w = canvas.shape[:2]
    if selection is not None and selection.shape != (h, w):
        raise ValueError(
            f"selection shape {selection.shape} does not match "
            f"canvas {(h, w)}",
        )

    ys, xs = np.indices((h, w), dtype=np.float32)
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    # Rotate pixel coords into the halftone-local frame and find the
    # signed offset to the nearest grid centre on each axis.
    local_x = xs * cos_a + ys * sin_a
    local_y = -xs * sin_a + ys * cos_a
    fx = local_x - np.round(local_x / spacing) * spacing
    fy = local_y - np.round(local_y / spacing) * spacing
    inside_dot = (fx * fx + fy * fy) <= (dot_radius * dot_radius)
    if selection is not None:
        inside_dot &= selection.astype(bool)
    if not inside_dot.any():
        return DamageRect(0, 0, 0, 0)

    canvas[inside_dot] = (color[0], color[1], color[2], 255)
    ys_hit, xs_hit = np.where(inside_dot)
    return DamageRect(
        x=int(xs_hit.min()),
        y=int(ys_hit.min()),
        w=int(xs_hit.max() - xs_hit.min() + 1),
        h=int(ys_hit.max() - ys_hit.min() + 1),
    )


# ---------------------------------------------------------------------------
# Internal line rasterisation
# ---------------------------------------------------------------------------


def _draw_thick_line(
    canvas: np.ndarray,
    x0: float, y0: float, x1: float, y1: float,
    line_width: int,
    fill: tuple[int, int, int, int],
) -> DamageRect:
    """Rasterise a straight line with integer thickness ``line_width``.

    Uses parametric step-and-round along the segment, plus a
    perpendicular offset for thickness > 1. Anti-aliasing is left to
    a future pass — the current renderer is intentionally crisp so
    speed-line strokes read as ink.
    """
    h, w = canvas.shape[:2]
    dx = x1 - x0
    dy = y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return DamageRect(0, 0, 0, 0)
    n_steps = int(length) + 1
    ts = np.linspace(0.0, 1.0, n_steps + 1)
    line_xs = x0 + dx * ts
    line_ys = y0 + dy * ts
    nx = -dy / length
    ny = dx / length
    accum = _EmptyDamage()
    half = (line_width - 1) / 2.0
    for offset in range(line_width):
        shift = offset - half
        ox = nx * shift
        oy = ny * shift
        xi = np.rint(line_xs + ox).astype(np.int64)
        yi = np.rint(line_ys + oy).astype(np.int64)
        valid = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
        if not valid.any():
            continue
        xs_clipped = xi[valid]
        ys_clipped = yi[valid]
        canvas[ys_clipped, xs_clipped] = fill
        accum.merge(DamageRect(
            x=int(xs_clipped.min()),
            y=int(ys_clipped.min()),
            w=int(xs_clipped.max() - xs_clipped.min() + 1),
            h=int(ys_clipped.max() - ys_clipped.min() + 1),
        ))
    return accum.to_rect()


# ---------------------------------------------------------------------------
# Damage-rect accumulator
# ---------------------------------------------------------------------------


class _EmptyDamage:
    """Mutable damage-rect builder — accumulates a union across calls."""

    def __init__(self) -> None:
        self._x0: int | None = None
        self._y0: int | None = None
        self._x1: int | None = None
        self._y1: int | None = None

    def merge(self, rect: DamageRect) -> None:
        if rect.is_empty:
            return
        x0, y0 = rect.x, rect.y
        x1, y1 = rect.x + rect.w, rect.y + rect.h
        if self._x0 is None:
            self._x0, self._y0, self._x1, self._y1 = x0, y0, x1, y1
            return
        self._x0 = min(self._x0, x0)
        self._y0 = min(self._y0, y0)
        self._x1 = max(self._x1, x1)
        self._y1 = max(self._y1, y1)

    def to_rect(self) -> DamageRect:
        if self._x0 is None:
            return DamageRect(0, 0, 0, 0)
        return DamageRect(
            x=self._x0, y=self._y0,
            w=self._x1 - self._x0, h=self._y1 - self._y0,
        )


def _check_canvas(canvas: np.ndarray) -> None:
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
