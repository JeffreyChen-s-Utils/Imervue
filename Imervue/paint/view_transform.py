"""Pan + zoom + rotation view transform for the canvas widget.

The canvas widget already tracks pan_x / pan_y / zoom; rotation
adds an extra degree of freedom that artists use to draw lines at
comfortable angles without re-orienting the tablet.

This module owns the math:

* :class:`ViewTransform` — frozen dataclass with ``pan_x`` /
  ``pan_y`` / ``zoom`` / ``rotation_deg``.
* :func:`screen_to_image` — translate a widget-space point into
  image-space pixels.
* :func:`image_to_screen` — inverse.
* :func:`rotate_around` — rotate the view by ``delta_deg`` while
  keeping a chosen pivot point stationary on screen.

Pure-math; the canvas widget owns the OpenGL glRotatef bridge.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

ROTATION_WRAP_DEGREES = 360.0


@dataclass(frozen=True)
class ViewTransform:
    """Pan + zoom + rotation, suitable for the GL canvas's view matrix.

    ``rotation_deg`` rotates the canvas counter-clockwise around the
    pivot — same convention as :func:`Imervue.paint.transform_handles`.
    Pan / zoom semantics match the existing canvas widget so the
    integration is a drop-in: pan is added, then a rotation around
    the centre, then a zoom.
    """

    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom: float = 1.0
    rotation_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.zoom <= 0:
            raise ValueError(f"zoom must be > 0, got {self.zoom!r}")


def screen_to_image(
    transform: ViewTransform, point: tuple[float, float],
) -> tuple[float, float]:
    """Convert a widget-space ``(x, y)`` into image-space pixels.

    Inverse of :func:`image_to_screen`. Stays a closed-form math
    expression so it's safe to call from a hot mouse-move handler.
    """
    sx, sy = float(point[0]), float(point[1])
    # Undo zoom first.
    if transform.zoom <= 0:
        return (0.0, 0.0)
    rel_x = (sx - transform.pan_x) / transform.zoom
    rel_y = (sy - transform.pan_y) / transform.zoom
    # Undo rotation around the origin (image-space (0, 0) was the
    # rotation pivot in this construction; the canvas widget centres
    # the rotation by adjusting pan after the spin).
    rad = math.radians(-transform.rotation_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return (
        rel_x * cos_a - rel_y * sin_a,
        rel_x * sin_a + rel_y * cos_a,
    )


def image_to_screen(
    transform: ViewTransform, point: tuple[float, float],
) -> tuple[float, float]:
    """Convert an image-space ``(x, y)`` into widget-space pixels."""
    ix, iy = float(point[0]), float(point[1])
    rad = math.radians(transform.rotation_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    rotated_x = ix * cos_a - iy * sin_a
    rotated_y = ix * sin_a + iy * cos_a
    return (
        rotated_x * transform.zoom + transform.pan_x,
        rotated_y * transform.zoom + transform.pan_y,
    )


def rotate_around(
    transform: ViewTransform,
    pivot_screen: tuple[float, float],
    delta_deg: float,
) -> ViewTransform:
    """Rotate the view by ``delta_deg`` keeping ``pivot_screen`` fixed.

    Standard "rotate around the cursor" UX: the canvas spins under
    the user's hand, so the screen pixel they're looking at stays
    where it was. Pan is recomputed so the pivot's image-space
    coordinate maps back to the same widget position.
    """
    # Find the image-space coordinate currently under the pivot.
    image_pivot = screen_to_image(transform, pivot_screen)
    # Apply the rotation; the pan / zoom values stay as-is for now.
    new_rotation = _wrap_rotation(transform.rotation_deg + float(delta_deg))
    candidate = replace(transform, rotation_deg=new_rotation)
    # After the rotation, the image_pivot would map to a new screen
    # position. Adjust pan so it lands back at pivot_screen.
    new_pivot = image_to_screen(candidate, image_pivot)
    pan_dx = pivot_screen[0] - new_pivot[0]
    pan_dy = pivot_screen[1] - new_pivot[1]
    return replace(
        candidate,
        pan_x=candidate.pan_x + pan_dx,
        pan_y=candidate.pan_y + pan_dy,
    )


def reset_rotation(transform: ViewTransform) -> ViewTransform:
    """Return a transform with the rotation cleared (pan / zoom kept)."""
    return replace(transform, rotation_deg=0.0)


def normalise_rotation(transform: ViewTransform) -> ViewTransform:
    """Wrap the rotation into ``(-180, 180]`` without changing visuals."""
    return replace(transform, rotation_deg=_wrap_rotation(transform.rotation_deg))


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _wrap_rotation(deg: float) -> float:
    """Wrap an angle into the canonical ``(-180, 180]`` range."""
    wrapped = ((float(deg) + 180.0) % ROTATION_WRAP_DEGREES) - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped
