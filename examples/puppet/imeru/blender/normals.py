"""Shading normals borrowed from simple shapes, the way 3D anime games light hair and faces.

Lit with its own normals, every lock of hair and every bump of the face would catch the
light on its own, and the cel thresholds would cut the result into noise. Anime games
instead copy the normals of a smooth stand-in shape (a ball around the head, a column
around the long hair) onto the detailed mesh, so the whole mass falls into light and
shade in one clean shape. A *field* here is that stand-in: ``field(x, y, depth)`` returns
the direction its surface faces at a canvas point (x right, y down, depth toward the
viewer), and :func:`borrow` blends it into a mesh's own normals.
"""
from __future__ import annotations

from collections.abc import Callable

import bpy
from mathutils import Vector

from common import smoothstep, to_px

Field = Callable[[float, float, float], tuple[float, float, float]]


def world_direction(dx: float, dy: float, depth: float) -> Vector:
    """A canvas-space direction as a unit world vector."""
    v = Vector((dx, -depth, -dy))
    return v.normalized() if v.length > 1e-12 else Vector((0.0, -1.0, 0.0))


def ellipsoid_field(centre: tuple[float, float, float],
                    radii: tuple[float, float, float]) -> Field:
    """The outward normal of an ellipsoid at canvas *centre* with pixel *radii*."""
    cx, cy, cd = centre
    rx, ry, rd = radii

    def field(x: float, y: float, depth: float) -> tuple[float, float, float]:
        return (x - cx) / rx ** 2, (y - cy) / ry ** 2, (depth - cd) / rd ** 2
    return field


def column_field(cx: float, cd: float, rx: float, rd: float) -> Field:
    """The outward normal of an upright elliptic column through canvas (cx, ., cd)."""
    def field(x: float, _y: float, depth: float) -> tuple[float, float, float]:
        return (x - cx) / rx ** 2, 0.0, (depth - cd) / rd ** 2
    return field


def blend_fields(top: Field, bottom: Field, y0: float, y1: float) -> Field:
    """*top* above canvas y *y0*, *bottom* below *y1*, eased in between."""
    def field(x: float, y: float, depth: float) -> tuple[float, float, float]:
        a = world_direction(*top(x, y, depth))
        b = world_direction(*bottom(x, y, depth))
        t = smoothstep(y0, y1, y)
        v = a.lerp(b, t)
        return v.x, -v.z, -v.y
    return field


def borrow(obj: bpy.types.Object, field: Field, amount: float = 0.8) -> None:
    """Shade *obj* with normals *amount* of the way from its own toward *field*'s."""
    mesh = obj.data
    normals = []
    for vert in mesh.vertices:
        x, y, depth = to_px(obj.matrix_world @ vert.co)
        target = world_direction(*field(x, y, depth))
        normals.append(vert.normal.lerp(target, amount).normalized())
    mesh.normals_split_custom_set_from_vertices(normals)


def face_light(obj: bpy.types.Object, toward_light: Vector) -> None:
    """Point every normal of *obj* at the light: it is lit all over except where shadowed.

    The face is shaded this way so the only shading the 3D render gives it is the shadow
    other parts cast on it; its own light and shade come from the face shadow map.
    """
    direction = toward_light.normalized()
    obj.data.normals_split_custom_set_from_vertices([direction] * len(obj.data.vertices))
