"""Geometry helpers for the deep-zoom minimap.

Pure-Python math extracted from ``GPUImageView`` so the minimap's on-screen
rectangle and click-to-navigate mapping are unit-testable without an OpenGL
context. The renderer and the mouse handler both go through these helpers so
the clickable area always matches what is drawn.
"""
from __future__ import annotations

MINIMAP_MAX_W = 180
MINIMAP_MAX_H = 140
MINIMAP_MARGIN = 12


def minimap_geometry(
    view_w: float,
    view_h: float,
    img_w: float,
    img_h: float,
    *,
    max_w: int = MINIMAP_MAX_W,
    max_h: int = MINIMAP_MAX_H,
    margin: int = MINIMAP_MARGIN,
) -> tuple[int, int, int, int]:
    """Return the minimap rectangle ``(x, y, w, h)`` in widget coordinates.

    The minimap keeps the image's aspect ratio, is capped at ``max_w`` /
    ``max_h``, and sits ``margin`` pixels in from the bottom-right corner.
    """
    aspect = img_w / max(img_h, 1)
    mm_w = max_w
    mm_h = int(mm_w / max(aspect, 0.1))
    if mm_h > max_h:
        mm_h = max_h
        mm_w = int(mm_h * aspect)
    mm_x = int(view_w - mm_w - margin)
    mm_y = int(view_h - mm_h - margin)
    return mm_x, mm_y, mm_w, mm_h


def point_in_rect(px: float, py: float, rect: tuple[float, float, float, float]) -> bool:
    """True if ``(px, py)`` lies within ``rect = (x, y, w, h)``."""
    x, y, w, h = rect
    return x <= px <= x + w and y <= py <= y + h


def recenter_offsets(
    click_x: float,
    click_y: float,
    rect: tuple[float, float, float, float],
    img_w: float,
    img_h: float,
    view_w: float,
    view_h: float,
    zoom: float,
) -> tuple[float, float]:
    """Map a click inside the minimap to deep-zoom pan offsets.

    The image point under the click is moved to the centre of the viewport.
    Returns ``(dz_offset_x, dz_offset_y)``; the click fraction is clamped to
    ``[0, 1]`` so a click on the minimap border can't pan past the image.
    """
    mm_x, mm_y, mm_w, mm_h = rect
    fx = min(1.0, max(0.0, (click_x - mm_x) / max(mm_w, 1e-9)))
    fy = min(1.0, max(0.0, (click_y - mm_y) / max(mm_h, 1e-9)))
    img_px = fx * img_w
    img_py = fy * img_h
    off_x = view_w / 2 - img_px * zoom
    off_y = view_h / 2 - img_py * zoom
    return off_x, off_y
