"""Pure geometry for the manual censor editor.

No Qt here — the editing operations (normalise a drag into a rectangle,
hit-test a point against the region stack, move / clamp a region, and map
between display and image coordinates) are plain functions so the interaction
logic is unit-testable without a widget or mouse events. The Qt canvas in
``_manual_dialog`` is a thin shell that calls these.

All regions are ``(x1, y1, x2, y2)`` in *image* pixels with x1<=x2, y1<=y2.
"""
from __future__ import annotations

# Smallest region edge (image px) worth keeping — a stray click that barely
# moves shouldn't leave a speck of a censor box.
MIN_REGION_EDGE = 6


def normalize_rect(x0: float, y0: float, x1: float, y1: float):
    """Order two drag corners into ``(x1, y1, x2, y2)`` with x1<=x2, y1<=y2."""
    return (int(min(x0, x1)), int(min(y0, y1)),
            int(max(x0, x1)), int(max(y0, y1)))


def is_valid_region(region, min_edge: int = MIN_REGION_EDGE) -> bool:
    """Whether *region* is large enough to keep (both edges >= *min_edge*)."""
    return (region[2] - region[0]) >= min_edge and (region[3] - region[1]) >= min_edge


def region_at(regions, x: float, y: float) -> int:
    """Index of the topmost region containing ``(x, y)``, or ``-1``.

    Iterates last-to-first so the most recently drawn region (painted on top)
    is the one hit — matching what the user sees.
    """
    for i in range(len(regions) - 1, -1, -1):
        rx1, ry1, rx2, ry2 = regions[i]
        if rx1 <= x <= rx2 and ry1 <= y <= ry2:
            return i
    return -1


def move_region(region, dx: float, dy: float):
    """Translate *region* by ``(dx, dy)`` (image px)."""
    return (int(region[0] + dx), int(region[1] + dy),
            int(region[2] + dx), int(region[3] + dy))


def clamp_region(region, width: int, height: int):
    """Clamp *region* to the ``width`` x ``height`` image bounds."""
    return (max(0, min(region[0], width)), max(0, min(region[1], height)),
            max(0, min(region[2], width)), max(0, min(region[3], height)))


def fit_scale(image_w: int, image_h: int, max_w: int, max_h: int) -> float:
    """Scale that fits ``image`` into ``max_w`` x ``max_h`` without upscaling."""
    if image_w <= 0 or image_h <= 0:
        return 1.0
    return min(max_w / image_w, max_h / image_h, 1.0)


def to_image_point(x: float, y: float, scale: float):
    """Display-space point → image-space point."""
    s = scale if scale > 0 else 1.0
    return (int(x / s), int(y / s))


def to_display_rect(region, scale: float):
    """Image-space region → display-space ``(x, y, w, h)`` for drawing."""
    x1, y1, x2, y2 = (int(v * scale) for v in region)
    return (x1, y1, x2 - x1, y2 - y1)
