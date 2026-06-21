"""Validate and repair skeletal-LBS bone-weight maps.

A drawable's ``bone_weights`` maps each ``bone_id`` to a per-vertex weight
list; linear blend skinning expects every vertex's weights to sum to ``1.0``
across all bones. Exported weight maps often violate this — negative weights,
a list shorter or longer than the vertex count, or per-vertex sums that round
to ``0.999`` — so these pure helpers detect and repair the damage. Vertices
with no influence at all (sum ``0``) are left alone: LBS keeps them at rest.

Pure Python — no Qt, no numpy. The runtime (``deformers.skeleton_lbs``) already
renormalises defensively; this is for *fixing the stored map* at author time.
"""
from __future__ import annotations

from collections.abc import Mapping

_DEFAULT_TOLERANCE = 0.05

BoneWeights = Mapping[str, list[float]]


def per_vertex_sums(bone_weights: BoneWeights, n_vertices: int) -> list[float]:
    """Return the total weight on each of *n_vertices* across all bones."""
    sums = [0.0] * n_vertices
    for weights in bone_weights.values():
        for i in range(min(n_vertices, len(weights))):
            sums[i] += float(weights[i])
    return sums


def is_normalised(
    bone_weights: BoneWeights, n_vertices: int,
    *, tolerance: float = _DEFAULT_TOLERANCE,
) -> bool:
    """True when every *influenced* vertex's weights sum to ~1.0.

    A vertex with no influence (sum ``0``) is allowed — LBS leaves it at rest —
    so it does not count as un-normalised.
    """
    return all(
        total <= 0.0 or abs(total - 1.0) <= tolerance
        for total in per_vertex_sums(bone_weights, n_vertices)
    )


def _fit_length(weights: list[float], n_vertices: int) -> list[float]:
    """Pad with zeros or truncate so the list is exactly *n_vertices* long."""
    if len(weights) < n_vertices:
        return weights + [0.0] * (n_vertices - len(weights))
    return weights[:n_vertices]


def needs_repair(bone_weights: BoneWeights, n_vertices: int) -> bool:
    """True when the map has negative weights, a wrong-length list, or a
    per-vertex sum that isn't ~1.0 (ignoring fully un-influenced vertices)."""
    for weights in bone_weights.values():
        if len(weights) != n_vertices or any(float(w) < 0.0 for w in weights):
            return True
    return not is_normalised(bone_weights, n_vertices)


def normalize_bone_weights(
    bone_weights: BoneWeights, n_vertices: int,
) -> dict[str, list[float]]:
    """Return a repaired copy: every influenced vertex sums to exactly 1.0.

    Per bone, negative weights are clamped to ``0`` and the list is padded /
    truncated to *n_vertices*. Per vertex, a non-zero sum is divided out; a zero
    sum stays zero. The input mapping is never mutated.
    """
    clamped = {
        bone_id: _fit_length([max(0.0, float(w)) for w in weights], n_vertices)
        for bone_id, weights in bone_weights.items()
    }
    sums = per_vertex_sums(clamped, n_vertices)
    return {
        bone_id: [
            (weight / sums[i]) if sums[i] > 0.0 else 0.0
            for i, weight in enumerate(weights)
        ]
        for bone_id, weights in clamped.items()
    }


def normalize_drawable_weights(drawable: object) -> bool:
    """Repair *drawable*'s ``bone_weights`` in place; return True if changed.

    A drawable with no ``bone_weights`` or no ``vertices`` is left untouched.
    Duck-typed (reads ``drawable.vertices`` / ``drawable.bone_weights``) so it
    works on any rig-like object.
    """
    weights = getattr(drawable, "bone_weights", None)
    vertices = getattr(drawable, "vertices", None)
    if not weights or not vertices:
        return False
    n_vertices = len(vertices)
    if not needs_repair(weights, n_vertices):
        return False
    drawable.bone_weights = normalize_bone_weights(weights, n_vertices)
    return True
