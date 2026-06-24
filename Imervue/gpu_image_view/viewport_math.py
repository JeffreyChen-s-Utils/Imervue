"""Screen <-> image coordinate transforms for the deep-zoom viewport.

The viewer maps image pixels to the screen as ``screen = image * zoom + offset``
(per axis); this module exposes that mapping and its inverse as 2-D point
transforms, plus the image-space rectangle currently visible on screen. The
1-D form matches ``view_animator.image_point_at``; this module stays Qt-free so
the geometry is unit-testable without a GL widget. Pure arithmetic.
"""
from __future__ import annotations

Point = tuple[float, float]
Size = tuple[float, float]
Rect = tuple[float, float, float, float]


def screen_to_image_point(point: Point, offset: Point, zoom: float) -> Point:
    """Map a screen point to image-space pixels (inverse of the viewer mapping).

    A zoom of 0 maps to the image origin rather than dividing by zero.
    """
    if not zoom:
        return (0.0, 0.0)
    return ((point[0] - offset[0]) / zoom, (point[1] - offset[1]) / zoom)


def image_to_screen_point(point: Point, offset: Point, zoom: float) -> Point:
    """Map an image-space point to screen coordinates."""
    return (point[0] * zoom + offset[0], point[1] * zoom + offset[1])


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def visible_image_rect(
    screen_size: Size, image_size: Size, offset: Point, zoom: float,
) -> Rect:
    """Return the image-space rectangle visible on screen, clamped to the image.

    ``(x0, y0, x1, y1)`` with ``x0 <= x1`` and ``y0 <= y1``; a zero-area rect
    when none of the image is on screen (or zoom is 0).
    """
    screen_w, screen_h = screen_size
    image_w, image_h = image_size
    top_left = screen_to_image_point((0.0, 0.0), offset, zoom)
    bottom_right = screen_to_image_point((screen_w, screen_h), offset, zoom)
    x0 = _clamp(min(top_left[0], bottom_right[0]), 0.0, image_w)
    x1 = _clamp(max(top_left[0], bottom_right[0]), 0.0, image_w)
    y0 = _clamp(min(top_left[1], bottom_right[1]), 0.0, image_h)
    y1 = _clamp(max(top_left[1], bottom_right[1]), 0.0, image_h)
    return (x0, y0, x1, y1)
