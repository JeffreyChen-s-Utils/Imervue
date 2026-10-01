"""Geometry builders for the Blender model of Imeru, all in canvas pixels.

``tube`` sweeps an elliptical cross-section along a path: the head, neck, torso and limbs
are tubes along a vertical or slanted axis, and every lock of hair is a flattened tube that
tapers to a point. ``sheet`` lays a flat 2D outline onto a surface (collar, cuffs, trims).
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import bmesh
import bpy
from mathutils import Vector, geometry

from common import PX, px, resample

#: Toward the viewer in world space (the camera looks along +Y).
TOWARD_VIEWER = Vector((0.0, -1.0, 0.0))


def link(obj: bpy.types.Object, collection: bpy.types.Collection) -> bpy.types.Object:
    """Put *obj* in *collection* (and nowhere else)."""
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)
    return obj


def _frames(points: list[Vector]) -> list[tuple[Vector, Vector]]:
    """A (side, toward-viewer) pair per path point, kept from flipping along the path."""
    frames = []
    previous = None
    for i in range(len(points)):
        a = points[max(0, i - 1)]
        b = points[min(len(points) - 1, i + 1)]
        tangent = (b - a).normalized() if (b - a).length > 1e-9 else Vector((0, 0, -1))
        side = tangent.cross(TOWARD_VIEWER)
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        up = side.cross(tangent).normalized()
        if up.dot(TOWARD_VIEWER) < 0:
            up = -up
        if previous is not None and side.dot(previous) < 0:
            side = -side
        previous = side
        frames.append((side, up))
    return frames


def tube(name: str, path: Sequence[Sequence[float]], radii: Sequence[Sequence[float]],
         material: bpy.types.Material, *, segments: int = 28, cap: bool = True,
         squash: Callable[[int, float], float] | None = None) -> bpy.types.Object:
    """A closed tube along *path* ``[(x, y, depth), ...]`` in canvas pixels.

    ``radii[i]`` is ``(across, front)`` or ``(across, front, back)``: the half width seen
    from the front and how far the surface bulges toward / away from the viewer. A zero
    radius closes the tube to a point. *squash(k, theta)* may scale ring vertex *k*.

    Every vertex carries two attributes the shaders paint with: ``along`` (0 at the start
    of the path, 1 at its end) and ``across`` (-1 at one edge seen from the front, 0 in the
    middle, 1 at the other edge).
    """
    points = [px(*p) for p in path]
    frames = _frames(points)
    bm = bmesh.new()
    along = bm.verts.layers.float.new("along")
    across_layer = bm.verts.layers.float.new("across")
    rings: list[list] = []
    last = max(1, len(points) - 1)
    for i, (point, (side, up), r) in enumerate(zip(points, frames, radii, strict=True)):
        across, front = r[0] / PX, r[1] / PX
        back = (r[2] if len(r) > 2 else r[1]) / PX
        if across < 1e-7 and front < 1e-7:
            pole = bm.verts.new(point)
            pole[along], pole[across_layer] = i / last, 0.0
            rings.append([pole])
            continue
        ring = []
        for k in range(segments):
            theta = 2 * math.pi * k / segments
            c, s = math.cos(theta), math.sin(theta)
            scale = squash(k, theta) if squash else 1.0
            depth = front if s >= 0 else back
            offset = side * (across * c * scale) + up * (depth * s * scale)
            vert = bm.verts.new(point + offset)
            vert[along], vert[across_layer] = i / last, c
            ring.append(vert)
        rings.append(ring)
    for a, b in zip(rings, rings[1:], strict=False):
        _bridge(bm, a, b)
    if cap:
        for ring in (rings[0], rings[-1]):
            if len(ring) > 2:
                bm.faces.new(ring)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _object(name, bm, material)


def _bridge(bm: bmesh.types.BMesh, a: list, b: list) -> None:
    if len(a) == 1 and len(b) == 1:
        return
    if len(a) == 1 or len(b) == 1:
        pole, ring = (a[0], b) if len(a) == 1 else (b[0], a)
        for k in range(len(ring)):
            bm.faces.new((pole, ring[k], ring[(k + 1) % len(ring)]))
        return
    n = len(a)
    for k in range(n):
        bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))


def _object(name: str, bm: bmesh.types.BMesh, material: bpy.types.Material) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def sheet(name: str, outline: Sequence[Sequence[float]], depth: Callable[[float, float], float],
          material: bpy.types.Material, *, thickness: float = 3.0, step: float = 14.0,
          holes: Sequence[Sequence[Sequence[float]]] = ()) -> bpy.types.Object:
    """A thin plate whose front outline is *outline* (canvas pixels), following *depth(x, y)*.

    The outline is triangulated together with a grid of interior points so the plate can
    bend; *thickness* pixels of Solidify give it a back and an edge for the line to catch.
    """
    loops = [list(outline), *[list(h) for h in holes]]
    verts, edges = [], []
    for loop in loops:
        start = len(verts)
        verts.extend(Vector((p[0], p[1])) for p in loop)
        edges.extend((start + i, start + (i + 1) % len(loop)) for i in range(len(loop)))
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    for shrink in (0.992, 0.978, 0.958, 0.93):
        verts.extend(Vector((cx + (p[0] - cx) * shrink, cy + (p[1] - cy) * shrink))
                     for p in resample(outline, max(24, len(outline))))
    x = min(xs) + step / 2
    while x < max(xs):
        y = min(ys) + step / 2
        while y < max(ys):
            verts.append(Vector((x, y)))
            y += step
        x += step
    out_verts, _, faces, *_ = geometry.delaunay_2d_cdt(verts, edges, [], 2, 1e-4)
    bm = bmesh.new()
    bverts = [bm.verts.new(px(v.x, v.y, depth(v.x, v.y))) for v in out_verts]
    for face in faces:
        try:
            bm.faces.new([bverts[i] for i in face])
        except ValueError:
            continue
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for face in bm.faces:
        if face.normal.dot(TOWARD_VIEWER) < 0:
            face.normal_flip()
    obj = _object(name, bm, material)
    if thickness > 0:
        solid = obj.modifiers.new("plate", "SOLIDIFY")
        solid.thickness = thickness / PX
        solid.offset = -1.0
        solid.use_even_offset = False
    return obj


def ellipsoid(name: str, centre: Sequence[float], radii: Sequence[float],
              material: bpy.types.Material, *, segments: int = 32) -> bpy.types.Object:
    """An ellipsoid at canvas *centre* ``(x, y, depth)`` with pixel *radii* ``(rx, ry, rdepth)``."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=1.0)
    for vert in bm.verts:
        vert.co = Vector((vert.co.x * radii[0], -vert.co.y * radii[2], vert.co.z * radii[1])) / PX
        vert.co += px(*centre)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _object(name, bm, material)


def torus(name: str, centre: Sequence[float], radius: float, thickness: float,
          material: bpy.types.Material, *, tilt: float = 0.0) -> bpy.types.Object:
    """A ring facing the viewer (tilted *tilt* radians about the vertical axis)."""
    path = []
    for k in range(65):
        a = 2 * math.pi * k / 64
        path.append((centre[0] + radius * math.cos(a) * math.cos(tilt),
                     centre[1] + radius * math.sin(a),
                     centre[2] + radius * math.cos(a) * math.sin(tilt)))
    return tube(name, path, [(thickness, thickness)] * len(path), material, segments=16,
                cap=False)


def star(name: str, centre: Sequence[float], outer: float, inner: float, depth: float,
         material: bpy.types.Material, *, points: int = 5, turn: float = 0.0) -> bpy.types.Object:
    """A five-pointed star plate facing the viewer, bevelled into a low pyramid."""
    bm = bmesh.new()
    cx, cy, cz = centre
    apex = bm.verts.new(px(cx, cy, cz + depth))
    rim = []
    for k in range(points * 2):
        a = turn - math.pi / 2 + math.pi * k / points
        r = outer if k % 2 == 0 else inner
        rim.append(bm.verts.new(px(cx + r * math.cos(a), cy + r * math.sin(a), cz)))
    for k in range(len(rim)):
        bm.faces.new((apex, rim[k], rim[(k + 1) % len(rim)]))
    bm.faces.new(list(reversed(rim)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = _object(name, bm, material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = False
    return obj
