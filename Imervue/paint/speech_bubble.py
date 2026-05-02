"""Speech-bubble rasteriser — pure-numpy ellipse + tail.

Comic / manga workflow tool: the user drags a rectangle on the
canvas, the workspace inscribes an ellipse inside it (white fill,
black border), then optionally extends a tail toward a follow-up
drag point so the bubble "points at" a character's mouth.

This module owns the maths only — the workspace tool dispatcher
collects pointer events and decides when to commit. Tests can
exercise every code path here without a Qt event loop.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_BORDER_PX = 3
DEFAULT_FILL = (255, 255, 255, 255)
DEFAULT_BORDER = (0, 0, 0, 255)
MIN_BUBBLE_DIM = 6


@dataclass(frozen=True)
class BubbleStyle:
    """Visual parameters for a speech bubble.

    ``shape`` selects the bubble silhouette: ``"ellipse"`` is the
    classic round speech bubble, ``"cloud"`` is the bumpy thought-
    cloud variant (currently rendered as a softened rounded rect).
    Future shapes plug in by extending the dispatcher in
    :func:`render_speech_bubble`.
    """

    fill: tuple[int, int, int, int] = DEFAULT_FILL
    border: tuple[int, int, int, int] = DEFAULT_BORDER
    border_px: int = DEFAULT_BORDER_PX
    shape: str = "ellipse"


def render_speech_bubble(
    canvas_shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    *,
    tail_to: tuple[int, int] | None = None,
    style: BubbleStyle | None = None,
) -> np.ndarray:
    """Return an HxWx4 RGBA layer with the bubble drawn on it.

    ``rect`` is ``(x, y, w, h)`` in canvas space — the bounding box
    of the bubble body. ``tail_to`` is an optional point in canvas
    space; when supplied a triangular tail is rendered from the
    nearest body edge to that point. The output's transparent pixels
    are exactly ``(0, 0, 0, 0)`` so the consumer can paste-blit it
    directly onto an existing layer.
    """
    style = style or BubbleStyle()
    if style.shape not in ("ellipse", "cloud"):
        raise ValueError(
            f"unknown shape {style.shape!r}; expected 'ellipse' or 'cloud'",
        )
    if style.border_px < 0:
        raise ValueError(f"border_px must be >= 0, got {style.border_px}")
    h, w = canvas_shape
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas_shape must be positive, got {canvas_shape}")
    x, y, rw, rh = rect
    if rw < MIN_BUBBLE_DIM or rh < MIN_BUBBLE_DIM:
        raise ValueError(
            f"rect dims must be >= {MIN_BUBBLE_DIM}, got w={rw} h={rh}",
        )
    layer = np.zeros((h, w, 4), dtype=np.uint8)
    body_mask = _bubble_body_mask((h, w), (x, y, rw, rh), shape=style.shape)
    tail_mask = (
        _tail_mask((h, w), (x, y, rw, rh), tail_to)
        if tail_to is not None else
        np.zeros((h, w), dtype=np.bool_)
    )
    fill_mask = body_mask | tail_mask
    border_mask = _border_mask(fill_mask, style.border_px) if style.border_px else (
        np.zeros((h, w), dtype=np.bool_)
    )
    # Paint fill first; border overrides where they overlap so the
    # outline stays crisp on top of the white body.
    layer[fill_mask] = style.fill
    layer[border_mask] = style.border
    return layer


# ---------------------------------------------------------------------------
# Internal mask helpers — every one returns an HxW bool array.
# ---------------------------------------------------------------------------


def _bubble_body_mask(
    canvas_shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    *,
    shape: str,
) -> np.ndarray:
    h, w = canvas_shape
    x, y, rw, rh = rect
    cy = y + rh / 2.0
    cx = x + rw / 2.0
    yy, xx = np.indices((h, w))
    rel_x = (xx - cx) / max(rw / 2.0, 1.0)
    rel_y = (yy - cy) / max(rh / 2.0, 1.0)
    if shape == "ellipse":
        return (rel_x * rel_x + rel_y * rel_y) <= 1.0
    # cloud → rounded rect: ellipse-ish but with squared shoulders
    # achieved via a higher exponent. Cheaper than convolving bumps
    # but visually distinct from a plain ellipse.
    return (np.abs(rel_x) ** 4 + np.abs(rel_y) ** 4) <= 1.0


def _tail_mask(
    canvas_shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    tip: tuple[int, int],
) -> np.ndarray:
    """Triangular tail from the bubble body toward ``tip``.

    The base of the triangle is anchored at the body edge nearest the
    tip (snapped to the bounding rect for simplicity). Width of the
    base scales with the bubble's smaller dimension so the tail looks
    proportionate on both tiny and huge bubbles.
    """
    h, w = canvas_shape
    x, y, rw, rh = rect
    cx = x + rw / 2.0
    cy = y + rh / 2.0
    tx, ty = float(tip[0]), float(tip[1])
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return np.zeros((h, w), dtype=np.bool_)
    # Base width — 30 % of the shorter axis, capped at 24 px.
    base_half = min(min(rw, rh) * 0.15, 12.0)
    # Decide whether the tail leaves the bubble through a horizontal
    # or vertical edge by comparing dx/rw vs dy/rh.
    if abs(dx) / max(rw, 1) >= abs(dy) / max(rh, 1):
        # Horizontal exit — left or right edge.
        edge_x = x + rw if dx > 0 else x
        base = ((edge_x, cy - base_half), (edge_x, cy + base_half))
    else:
        # Vertical exit — top or bottom edge.
        edge_y = y + rh if dy > 0 else y
        base = ((cx - base_half, edge_y), (cx + base_half, edge_y))
    return _triangle_mask((h, w), base[0], base[1], (tx, ty))


def _triangle_mask(
    canvas_shape: tuple[int, int],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> np.ndarray:
    """Fill a triangle using the half-plane test.

    Walks every pixel and checks the sign of three half-plane
    equations. Cheap enough at typical bubble-tail sizes; if the
    bubble ever grows past the whole canvas this is still O(h*w)
    which numpy parallelises trivially.
    """
    h, w = canvas_shape
    yy, xx = np.indices((h, w))

    def _sign(p1, p2, p3):
        return (
            (p1[0] - p3[0]) * (p2[1] - p3[1])
            - (p2[0] - p3[0]) * (p1[1] - p3[1])
        )

    d1 = _sign((xx, yy), a, b)
    d2 = _sign((xx, yy), b, c)
    d3 = _sign((xx, yy), c, a)
    has_neg = (d1 < 0) | (d2 < 0) | (d3 < 0)
    has_pos = (d1 > 0) | (d2 > 0) | (d3 > 0)
    return ~(has_neg & has_pos)


def _border_mask(fill_mask: np.ndarray, border_px: int) -> np.ndarray:
    """Pixels that are on the boundary of ``fill_mask`` to a depth
    of ``border_px``.

    Implementation: erode the fill by ``border_px`` and XOR — the
    result is the rim. Erosion is done with simple 4-connected
    iteration so we don't pull scipy in for one filter.
    """
    if border_px <= 0:
        return np.zeros_like(fill_mask, dtype=np.bool_)
    eroded = fill_mask.copy()
    for _ in range(border_px):
        # Shift in the four cardinal directions and AND — a pixel
        # survives erosion only if all four neighbours are inside.
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
