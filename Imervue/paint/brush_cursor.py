"""Brush-footprint cursor preview generator.

The canvas widget shows a translucent ring at the cursor so the
user can see exactly where the next dab will land. This module is
the pure-numpy half — produces an HxWx4 RGBA buffer with the ring
rasterised at the requested cursor position; the widget blits it
on top of the layer composite as a hover overlay.

Two ring modes:

* outer ring at the brush radius (always rendered);
* an optional inner ring at ``hardness_radius`` so the user sees
  the brush's hard core boundary when working with a soft brush.
"""
from __future__ import annotations

import numpy as np

DEFAULT_CURSOR_COLOR = (0, 0, 0, 200)
# Quick-mask brush cursor — translucent red, 50 % alpha, matches the
# overlay colour rendered by ``quick_mask.quick_mask_overlay`` so the
# user knows their next dab edits the mask, not the layer pixels.
QUICK_MASK_CURSOR_COLOR = (255, 0, 0, 128)
MAX_RADIUS = 4096
MIN_THICKNESS = 1
MAX_THICKNESS = 64


def cursor_color_for_state(
    foreground_rgb: tuple[int, int, int],
    *,
    quick_mask_active: bool = False,
    foreground_alpha: int = 200,
) -> tuple[int, int, int, int]:
    """Pick the cursor ring colour given the active state.

    When quick mask is active the cursor switches to the mask-edit
    red so the user has a visual cue that the brush is editing the
    selection instead of the layer pixels. Otherwise the cursor
    inherits the user's foreground colour with the standard alpha.
    """
    if quick_mask_active:
        return QUICK_MASK_CURSOR_COLOR
    r, g, b = foreground_rgb
    return (int(r), int(g), int(b), int(foreground_alpha))


def render_cursor_ring(
    canvas_size: tuple[int, int],
    cx: float,
    cy: float,
    radius: float,
    *,
    color: tuple[int, int, int, int] = DEFAULT_CURSOR_COLOR,
    thickness: int = 1,
    inner_radius: float | None = None,
) -> np.ndarray:
    """Render a circle outline at ``(cx, cy)`` onto a fresh transparent
    buffer.

    ``thickness`` is the band width in pixels (1 = single-pixel
    outline, 3 = thicker ring etc.). ``inner_radius`` (optional) draws
    a second concentric outline; useful for showing the brush's hard
    core inside a soft falloff.
    """
    h, w = canvas_size
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas_size must be positive, got {canvas_size!r}")
    if radius < 0:
        raise ValueError(f"radius must be >= 0, got {radius!r}")
    if radius > MAX_RADIUS:
        raise ValueError(
            f"radius must be <= {MAX_RADIUS}, got {radius!r}",
        )
    if not MIN_THICKNESS <= int(thickness) <= MAX_THICKNESS:
        raise ValueError(
            f"thickness must be in [{MIN_THICKNESS}, {MAX_THICKNESS}], "
            f"got {thickness!r}",
        )

    out = np.zeros((h, w, 4), dtype=np.uint8)
    if radius == 0 and inner_radius is None:
        return out

    ys, xs = np.indices((h, w), dtype=np.float32)
    dx = xs - float(cx)
    dy = ys - float(cy)
    dist = np.sqrt(dx * dx + dy * dy)
    band = float(thickness) / 2.0

    if radius > 0:
        outer_mask = (dist >= radius - band) & (dist <= radius + band)
        out[outer_mask] = color

    if inner_radius is not None and inner_radius > 0:
        if 0 < radius <= inner_radius:
            raise ValueError(
                f"inner_radius {inner_radius} must be < radius {radius}",
            )
        inner_mask = (
            (dist >= inner_radius - band)
            & (dist <= inner_radius + band)
        )
        out[inner_mask] = color
    return out


def cursor_bbox(
    cx: float, cy: float, radius: float, *, thickness: int = 1,
) -> tuple[int, int, int, int]:
    """Return the smallest pixel rect that contains the cursor ring.

    Useful when the canvas widget wants to limit the redraw region —
    no need to repaint the whole canvas when only a small area
    around the cursor changed."""
    band = max(1, int(thickness)) / 2.0
    half = float(radius) + band + 1.0
    x0 = int(np.floor(cx - half))
    y0 = int(np.floor(cy - half))
    x1 = int(np.ceil(cx + half))
    y1 = int(np.ceil(cy + half))
    return (x0, y0, x1 - x0, y1 - y0)
