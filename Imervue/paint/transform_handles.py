"""On-canvas transform handles — pure math half.

The :mod:`Imervue.paint.selection_transform` module already does the
heavy lifting of warping selected pixels by a scale / rotation /
translation triple. What was missing was the user affordance: an
oriented bounding box with drag handles that update the parameters
in place.

This module owns the geometry — handle positions, hit testing, and
delta application. The Qt overlay paint + mouse routing live in the
canvas widget; keeping the math here means the contract is testable
without a display server.

Conventions
-----------

* The transform box sits in image-space pixels. Its ``rotation_deg``
  rotates clockwise around the box centre (matching MediBang /
  Photoshop's display).
* Eight bounding handles + one rotation handle:

    NW --- N --- NE
     |           |
     W   centre  E
     |           |
    SW --- S --- SE

  plus a ``ROTATE`` handle drawn above the N edge.
* :func:`hit_test` returns ``None`` when no handle is within the
  click tolerance. Callers fall back to "drag the body to move".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import cast

# Handle kind constants — strings rather than an Enum so JSON
# round-trips don't need a custom encoder.
HANDLE_NW = "nw"
HANDLE_N = "n"
HANDLE_NE = "ne"
HANDLE_E = "e"
HANDLE_SE = "se"
HANDLE_S = "s"
HANDLE_SW = "sw"
HANDLE_W = "w"
HANDLE_ROTATE = "rotate"
HANDLE_BODY = "body"

CORNER_HANDLES = (HANDLE_NW, HANDLE_NE, HANDLE_SE, HANDLE_SW)
EDGE_HANDLES = (HANDLE_N, HANDLE_E, HANDLE_S, HANDLE_W)
ALL_BOX_HANDLES = (*CORNER_HANDLES, *EDGE_HANDLES, HANDLE_ROTATE)

DEFAULT_HANDLE_RADIUS = 8.0
ROTATE_HANDLE_OFFSET = 28.0   # pixels above the N edge in box-local space
MIN_BOX_SIZE = 4.0            # don't let a drag collapse the box past this


@dataclass(frozen=True)
class TransformBox:
    """Oriented bounding box for a selection or layer.

    ``cx`` / ``cy`` is the centre in image-space pixels. ``width`` /
    ``height`` are the box's local extents (un-rotated). Stored as a
    centre + size pair (rather than a top-left + size) so a rotation
    pivots about the visual middle the way users expect.
    """

    cx: float
    cy: float
    width: float
    height: float
    rotation_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.width < MIN_BOX_SIZE:
            raise ValueError(
                f"width must be >= {MIN_BOX_SIZE}, got {self.width!r}",
            )
        if self.height < MIN_BOX_SIZE:
            raise ValueError(
                f"height must be >= {MIN_BOX_SIZE}, got {self.height!r}",
            )


def from_rect(x: float, y: float, w: float, h: float) -> TransformBox:
    """Build a :class:`TransformBox` from an axis-aligned (x, y, w, h)."""
    return TransformBox(
        cx=float(x) + float(w) / 2.0,
        cy=float(y) + float(h) / 2.0,
        width=float(w),
        height=float(h),
        rotation_deg=0.0,
    )


def handle_positions(box: TransformBox) -> dict[str, tuple[float, float]]:
    """Return the screen-space ``(x, y)`` of every handle.

    The box's local frame puts the centre at origin and the corners
    at ``(±width/2, ±height/2)``. We rotate each handle by the box's
    rotation around the centre and add the centre back in.
    """
    half_w = box.width / 2.0
    half_h = box.height / 2.0
    rad = math.radians(box.rotation_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    def project(local_x: float, local_y: float) -> tuple[float, float]:
        return (
            box.cx + local_x * cos_a - local_y * sin_a,
            box.cy + local_x * sin_a + local_y * cos_a,
        )

    return {
        HANDLE_NW: project(-half_w, -half_h),
        HANDLE_N: project(0.0, -half_h),
        HANDLE_NE: project(half_w, -half_h),
        HANDLE_E: project(half_w, 0.0),
        HANDLE_SE: project(half_w, half_h),
        HANDLE_S: project(0.0, half_h),
        HANDLE_SW: project(-half_w, half_h),
        HANDLE_W: project(-half_w, 0.0),
        HANDLE_ROTATE: project(0.0, -half_h - ROTATE_HANDLE_OFFSET),
    }


def hit_test(
    box: TransformBox,
    point: tuple[float, float],
    *,
    handle_radius: float = DEFAULT_HANDLE_RADIUS,
) -> str | None:
    """Return the handle under ``point``, or ``None`` if outside.

    A click on the box body (no handle) returns :data:`HANDLE_BODY`
    so the caller can route it as a translation drag instead of
    re-running its own hit test.
    """
    px, py = float(point[0]), float(point[1])
    threshold_sq = float(handle_radius) ** 2
    positions = handle_positions(box)
    for name, (hx, hy) in positions.items():
        dx = px - hx
        dy = py - hy
        if dx * dx + dy * dy <= threshold_sq:
            return name
    if _point_inside_oriented_box(box, (px, py)):
        return HANDLE_BODY
    return None


def apply_handle_drag(
    box: TransformBox,
    handle: str,
    delta: tuple[float, float],
) -> TransformBox:
    """Return a new box with ``delta`` applied through ``handle``.

    * Body drag → translate.
    * Corner / edge → resize from the opposite corner / edge.
    * Rotate → angle from centre to mouse position.

    The drag delta is the in-image-space movement since the last
    update; the caller accumulates per-mousemove and feeds the
    cumulative or per-tick delta as appropriate.
    """
    if handle == HANDLE_BODY:
        return cast(
            TransformBox,
            replace(box, cx=box.cx + delta[0], cy=box.cy + delta[1]),
        )
    if handle == HANDLE_ROTATE:
        return _apply_rotate(box, delta)
    if handle in CORNER_HANDLES or handle in EDGE_HANDLES:
        return _apply_resize(box, handle, delta)
    raise ValueError(
        f"unknown handle {handle!r}; expected one of {ALL_BOX_HANDLES} or "
        f"{HANDLE_BODY!r}",
    )


# ---------------------------------------------------------------------------
# Internal math helpers
# ---------------------------------------------------------------------------


def _world_to_local(
    box: TransformBox, point: tuple[float, float],
) -> tuple[float, float]:
    """Project ``point`` into the box's un-rotated local frame."""
    rad = math.radians(-box.rotation_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    rel_x = float(point[0]) - box.cx
    rel_y = float(point[1]) - box.cy
    return (rel_x * cos_a - rel_y * sin_a, rel_x * sin_a + rel_y * cos_a)


def _point_inside_oriented_box(
    box: TransformBox, point: tuple[float, float],
) -> bool:
    local_x, local_y = _world_to_local(box, point)
    return (
        abs(local_x) <= box.width / 2.0
        and abs(local_y) <= box.height / 2.0
    )


def _apply_rotate(
    box: TransformBox, delta: tuple[float, float],
) -> TransformBox:
    """Rotate by the angle between the rotate handle's previous and
    current world position. The caller feeds the delta as a vector
    from the previous position; we recover the cumulative angle by
    measuring the new handle position relative to the centre."""
    handle_x, handle_y = handle_positions(box)[HANDLE_ROTATE]
    new_x = handle_x + delta[0]
    new_y = handle_y + delta[1]
    new_angle = math.degrees(math.atan2(
        new_y - box.cy, new_x - box.cx,
    )) + 90.0   # +90 because the rotate handle sits at -90° in local space
    return cast(TransformBox, replace(box, rotation_deg=new_angle))


def _apply_resize(
    box: TransformBox, handle: str, delta: tuple[float, float],
) -> TransformBox:
    """Resize from the opposite anchor by ``delta`` (world-space)."""
    # Convert the delta into the box's local frame so a 45°-rotated
    # box still resizes along its own axes.
    local_dx, local_dy = _world_to_local(
        box, (box.cx + delta[0], box.cy + delta[1]),
    )
    new_width, new_height = box.width, box.height
    cx_shift_local_x = 0.0
    cx_shift_local_y = 0.0
    if "w" in handle:
        new_width = max(MIN_BOX_SIZE, box.width - local_dx)
        cx_shift_local_x = (box.width - new_width) / 2.0
    if "e" in handle:
        new_width = max(MIN_BOX_SIZE, box.width + local_dx)
        cx_shift_local_x = (new_width - box.width) / 2.0
    if "n" in handle:
        new_height = max(MIN_BOX_SIZE, box.height - local_dy)
        cx_shift_local_y = (box.height - new_height) / 2.0
    if "s" in handle:
        new_height = max(MIN_BOX_SIZE, box.height + local_dy)
        cx_shift_local_y = (new_height - box.height) / 2.0
    # Centre shift is in local space; rotate back into world space
    # before adding to (cx, cy).
    rad = math.radians(box.rotation_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    world_shift_x = cx_shift_local_x * cos_a - cx_shift_local_y * sin_a
    world_shift_y = cx_shift_local_x * sin_a + cx_shift_local_y * cos_a
    return cast(TransformBox, replace(
        box,
        cx=box.cx + world_shift_x,
        cy=box.cy + world_shift_y,
        width=new_width,
        height=new_height,
    ))
