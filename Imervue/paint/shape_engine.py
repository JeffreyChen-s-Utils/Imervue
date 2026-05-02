"""Shape rasterisers — rectangle / ellipse / line / polygon.

Pure-numpy primitives that paint geometric shapes onto an HxWx4
RGBA canvas. Each helper supports two modes:

* ``"fill"`` — solid interior, no border (current FG colour).
* ``"stroke"`` — only the perimeter, ``stroke_width`` pixels wide.
* ``"both"`` — fill + stroke (border outside the fill).

Coordinates are floating-point and clipped to the canvas bounds so
a shape that extends past the edge silently truncates. Anti-aliasing
is intentionally **omitted** — a shape tool that produces hard edges
is the convention in MediBang / Photoshop and matches the rest of
Imervue's pixel-snapped raster brushes.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

SHAPE_MODES = ("fill", "stroke", "both")
DEFAULT_MODE = "fill"
DEFAULT_STROKE_WIDTH = 2

MIN_SHAPE_DIM = 1


def rasterise_rect(
    canvas: np.ndarray,
    x: float, y: float, w: float, h: float,
    color: tuple[int, int, int, int],
    *, mode: str = DEFAULT_MODE,
    stroke_width: int = DEFAULT_STROKE_WIDTH,
) -> bool:
    """Paint an axis-aligned rectangle onto ``canvas`` in place.

    Returns ``True`` if any pixel was written. ``w``/``h`` may be
    negative (the helper normalises to a positive rect). Bounding
    box is clipped to the canvas.
    """
    _validate_canvas(canvas)
    _validate_mode(mode)
    rect = _normalise_rect(x, y, w, h, canvas.shape[:2])
    if rect is None:
        return False
    rx, ry, rw, rh = rect
    h_canvas, w_canvas = canvas.shape[:2]
    fill_mask = np.zeros((h_canvas, w_canvas), dtype=np.bool_)
    fill_mask[ry:ry + rh, rx:rx + rw] = True
    return _paint_masks(
        canvas, fill_mask, color, mode=mode, stroke_width=stroke_width,
    )


def rasterise_ellipse(
    canvas: np.ndarray,
    cx: float, cy: float, rx: float, ry: float,
    color: tuple[int, int, int, int],
    *, mode: str = DEFAULT_MODE,
    stroke_width: int = DEFAULT_STROKE_WIDTH,
) -> bool:
    """Paint an ellipse centred at (cx, cy) with semi-axes (rx, ry).

    A circle is just ``rx == ry``. Both radii are forced to a minimum
    of half a pixel so a zero-size drag can't divide-by-zero in the
    ellipse equation.
    """
    _validate_canvas(canvas)
    _validate_mode(mode)
    rx = max(0.5, abs(float(rx)))
    ry = max(0.5, abs(float(ry)))
    h_canvas, w_canvas = canvas.shape[:2]
    yy, xx = np.indices((h_canvas, w_canvas))
    norm = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    fill_mask = norm <= 1.0
    return _paint_masks(
        canvas, fill_mask, color, mode=mode, stroke_width=stroke_width,
    )


def rasterise_line(
    canvas: np.ndarray,
    x0: float, y0: float, x1: float, y1: float,
    color: tuple[int, int, int, int],
    *, width: int = DEFAULT_STROKE_WIDTH,
) -> bool:
    """Paint a line of thickness ``width`` between two points.

    Implemented as a stamped disk along the segment — same kernel as
    the brush tool but a hard-edged disc so the stroke matches the
    other shape tools' visual style.
    """
    _validate_canvas(canvas)
    if width < MIN_SHAPE_DIM:
        raise ValueError(f"width must be >= {MIN_SHAPE_DIM}, got {width}")
    h_canvas, w_canvas = canvas.shape[:2]
    radius = max(0.5, width / 2.0)
    dx = float(x1) - float(x0)
    dy = float(y1) - float(y0)
    length = math.hypot(dx, dy)
    # Always stamp at least the two endpoints so a click without
    # drag still leaves a visible dot.
    spacing = max(1.0, radius * 0.5)
    n_steps = max(1, int(math.ceil(length / spacing)))
    yy, xx = np.indices((h_canvas, w_canvas))
    fill_mask = np.zeros((h_canvas, w_canvas), dtype=np.bool_)
    for i in range(n_steps + 1):
        t = i / n_steps if n_steps > 0 else 0
        sx = float(x0) + dx * t
        sy = float(y0) + dy * t
        fill_mask |= ((xx - sx) ** 2 + (yy - sy) ** 2) <= (radius * radius)
    if not fill_mask.any():
        return False
    canvas[fill_mask] = color
    return True


def rasterise_polygon(
    canvas: np.ndarray,
    points: Sequence[tuple[float, float]],
    color: tuple[int, int, int, int],
    *, mode: str = DEFAULT_MODE,
    stroke_width: int = DEFAULT_STROKE_WIDTH,
) -> bool:
    """Paint a closed polygon defined by ``points``.

    Polygons with fewer than three points fall back to a line (two
    points) or a single dot (one point) — matches the user gesture:
    clicking once and committing should still leave a visible dab.
    """
    _validate_canvas(canvas)
    _validate_mode(mode)
    if not points:
        return False
    if len(points) == 1:
        return rasterise_line(
            canvas, points[0][0], points[0][1],
            points[0][0], points[0][1],
            color, width=max(stroke_width, 1),
        )
    if len(points) == 2:
        return rasterise_line(
            canvas, points[0][0], points[0][1],
            points[1][0], points[1][1],
            color, width=max(stroke_width, 1),
        )
    from Imervue.paint.selection import polygon_mask
    h_canvas, w_canvas = canvas.shape[:2]
    fill_mask = polygon_mask(h_canvas, w_canvas, list(points))
    return _paint_masks(
        canvas, fill_mask, color, mode=mode, stroke_width=stroke_width,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _validate_canvas(canvas: np.ndarray) -> None:
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape}"
            f" {canvas.dtype}",
        )


def _validate_mode(mode: str) -> None:
    if mode not in SHAPE_MODES:
        raise ValueError(
            f"mode must be one of {SHAPE_MODES}, got {mode!r}",
        )


def _normalise_rect(
    x: float, y: float, w: float, h: float,
    canvas_shape: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    """Convert a possibly-flipped rect into a positive (x, y, w, h)
    clipped to the canvas. Returns ``None`` for a zero-area rect."""
    h_canvas, w_canvas = canvas_shape
    rx = int(round(min(x, x + w)))
    ry = int(round(min(y, y + h)))
    rw = int(round(abs(w)))
    rh = int(round(abs(h)))
    if rw < MIN_SHAPE_DIM or rh < MIN_SHAPE_DIM:
        return None
    # Clip to canvas.
    rx_c = max(0, rx)
    ry_c = max(0, ry)
    rw_c = max(0, min(rx + rw, w_canvas) - rx_c)
    rh_c = max(0, min(ry + rh, h_canvas) - ry_c)
    if rw_c < MIN_SHAPE_DIM or rh_c < MIN_SHAPE_DIM:
        return None
    return rx_c, ry_c, rw_c, rh_c


def _paint_masks(
    canvas: np.ndarray,
    fill_mask: np.ndarray,
    color: tuple[int, int, int, int],
    *, mode: str,
    stroke_width: int,
) -> bool:
    """Apply ``fill_mask`` (and a derived stroke mask) to ``canvas``.

    Returns ``True`` if any pixel changed. ``stroke_width`` < 1 with
    ``mode="stroke"`` would produce no visible output; the caller is
    expected to clamp upstream but we tolerate it here by treating it
    as a no-op.
    """
    if not fill_mask.any():
        return False
    if mode == "fill":
        canvas[fill_mask] = color
        return True
    stroke_mask = _border_of(fill_mask, max(0, int(stroke_width)))
    if mode == "stroke":
        if not stroke_mask.any():
            return False
        canvas[stroke_mask] = color
        return True
    # "both": paint the fill first, then the stroke on top so the
    # border colour wins where they overlap.
    canvas[fill_mask] = color
    if stroke_mask.any():
        canvas[stroke_mask] = color
    return True


def _border_of(fill_mask: np.ndarray, width: int) -> np.ndarray:
    """Return the inner-rim of ``fill_mask`` to a depth of ``width``.

    Implementation: erode the fill mask by ``width`` 4-connected
    iterations and XOR the result. ``width <= 0`` returns an empty
    mask so callers never have to special-case the no-stroke path.
    """
    if width <= 0:
        return np.zeros_like(fill_mask, dtype=np.bool_)
    eroded = fill_mask.copy()
    for _ in range(width):
        up = np.zeros_like(eroded)
        up[:-1] = eroded[1:]
        down = np.zeros_like(eroded)
        down[1:] = eroded[:-1]
        left = np.zeros_like(eroded)
        left[:, :-1] = eroded[:, 1:]
        right = np.zeros_like(eroded)
        right[:, 1:] = eroded[:, :-1]
        eroded = eroded & up & down & left & right
    return fill_mask & ~eroded
