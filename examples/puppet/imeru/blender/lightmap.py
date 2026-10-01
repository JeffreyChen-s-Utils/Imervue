"""Baked ambient occlusion: the "always in shadow" map of anime-game cel shading.

Anime games paint a light map onto each character so that creases, the hair under other
hair and the cloth under the collar stay in shade whatever the light does. Here it is
baked instead: every vertex casts a fan of rays over its hemisphere, and the share that
escapes within ``reach`` pixels becomes its ``ao`` attribute (1 open, 0 buried), which the
cel shader multiplies into the light it sees (``toon(..., occlusion=...)``).

Each layer is only occluded by the layers that move with it in the rig, so a shadow never
stays behind when, say, an arm is raised away from the body.
"""
from __future__ import annotations

import math
import random

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from common import PX

#: Which layers occlude which: (receiving layers, occluding layers).
GROUPS = (
    (("bangs", "side_lock_l", "side_lock_r", "back_hair", "ahoge"),
     ("bangs", "side_lock_l", "side_lock_r", "back_hair", "ahoge", "face", "hairpin")),
    (("body", "collar", "ribbon"), ("body", "collar", "ribbon")),
    (("upper_arm_l", "forearm_l"), ("upper_arm_l", "forearm_l")),
    (("upper_arm_r", "forearm_r"), ("upper_arm_r", "forearm_r")),
)
RAYS = 32
REACH_PX = 60.0
#: Neighbour-averaging passes that take the speckle out of the ray count.
SMOOTHING = 3
#: Rays start this far off the surface so they don't hit the face they leave from.
LIFT_PX = 0.6


def _directions(count: int) -> list[Vector]:
    """Cosine-weighted directions over the +Z hemisphere (fixed seed: same bake every run)."""
    rng = random.Random(7)
    out = []
    for i in range(count):
        u = (i + rng.random()) / count
        phi = 2 * math.pi * rng.random()
        r = math.sqrt(u)
        out.append(Vector((r * math.cos(phi), r * math.sin(phi), math.sqrt(1 - u))))
    return out


def _frame(normal: Vector) -> tuple[Vector, Vector]:
    helper = Vector((1.0, 0.0, 0.0)) if abs(normal.x) < 0.9 else Vector((0.0, 1.0, 0.0))
    tangent = normal.cross(helper).normalized()
    return tangent, normal.cross(tangent)


def _tree(objects: list[bpy.types.Object]) -> BVHTree:
    """A ray-cast tree over *objects* as rendered, without their outline hulls."""
    for obj in objects:
        hull = obj.modifiers.get("outline")
        if hull:
            hull.show_viewport = False
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    verts: list[Vector] = []
    polys: list[list[int]] = []
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        base = len(verts)
        verts.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        polys.extend([base + i for i in poly.vertices] for poly in mesh.polygons)
        evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def _occlusion(obj: bpy.types.Object, tree: BVHTree, directions: list[Vector]) -> list[float]:
    reach, lift = REACH_PX / PX, LIFT_PX / PX
    values = []
    for vert in obj.data.vertices:
        normal = vert.normal
        tangent, bitangent = _frame(normal)
        origin = obj.matrix_world @ vert.co + normal * lift
        hits = 0
        for d in directions:
            ray = tangent * d.x + bitangent * d.y + normal * d.z
            if tree.ray_cast(origin, ray, reach)[0] is not None:
                hits += 1
        values.append(1.0 - hits / len(directions))
    return values


def bake(collections: dict[str, bpy.types.Collection]) -> None:
    """Give every mesh an ``ao`` attribute: baked for the layers in :data:`GROUPS`, else 1."""
    directions = _directions(RAYS)
    baked: set[str] = set()
    for receivers, occluders in GROUPS:
        sources = [obj for name in occluders if name in collections
                   for obj in collections[name].all_objects if obj.type == "MESH"]
        tree = _tree(sources)
        for name in receivers:
            if name not in collections:
                continue
            for obj in collections[name].all_objects:
                if obj.type == "MESH":
                    _store(obj, _smooth(obj.data, _occlusion(obj, tree, directions)))
                    baked.add(obj.name)
    for collection in collections.values():
        for obj in collection.all_objects:
            if obj.type == "MESH" and obj.name not in baked:
                _store(obj, [1.0] * len(obj.data.vertices))


def _smooth(mesh: bpy.types.Mesh, values: list[float]) -> list[float]:
    """Average every vertex with its neighbours :data:`SMOOTHING` times."""
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int64)
    mesh.edges.foreach_get("vertices", edges)
    a, b = edges[0::2], edges[1::2]
    ao = np.asarray(values, dtype=np.float64)
    degree = np.bincount(np.concatenate([a, b]), minlength=len(ao)) + 1.0
    for _ in range(SMOOTHING):
        total = ao.copy()
        np.add.at(total, a, ao[b])
        np.add.at(total, b, ao[a])
        ao = total / degree
    return ao.tolist()


def _store(obj: bpy.types.Object, values: list[float]) -> None:
    attribute = obj.data.attributes.get("ao") or obj.data.attributes.new("ao", "FLOAT", "POINT")
    attribute.data.foreach_set("value", values)
