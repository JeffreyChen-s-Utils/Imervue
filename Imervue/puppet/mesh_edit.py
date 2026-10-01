"""Pure-Python mesh-edit operations on a :class:`Drawable`.

The canvas's mesh-edit tool calls into here when the user clicks /
drags vertices. Every function returns a new vertex index (or
``None``) so the caller can keep selection state outside the document.
Qt-free; the actual mouse handling lives in the canvas widget.
"""
from __future__ import annotations

from collections.abc import Sequence

from Imervue.puppet.document import Drawable, PuppetDocument

_MORPH_SIDES = ("delta_at_min", "delta_at_max")


def find_vertex_at(
    drawable: Drawable, x: float, y: float, *, radius: float = 8.0,
) -> int | None:
    """Return the index of the closest vertex within ``radius`` pixels
    of ``(x, y)`` in canvas-space, or ``None`` if no vertex is close
    enough."""
    if not drawable.vertices:
        return None
    best_idx: int | None = None
    best_dist_sq = float(radius) ** 2
    for idx, (vx, vy) in enumerate(drawable.vertices):
        dx = float(vx) - float(x)
        dy = float(vy) - float(y)
        d_sq = dx * dx + dy * dy
        if d_sq <= best_dist_sq:
            best_dist_sq = d_sq
            best_idx = idx
    return best_idx


def _invalidate_rest_cache(drawable: Drawable) -> None:
    """Drop runtime's memoised numpy rest-vertex cache after an edit.

    ``runtime._rest_vertices_array`` caches ``drawable._np_rest_vertices`` and
    never invalidates it, so a vertex edit was composed from the stale cache and
    stayed invisible on any parameterised rig. Clear it so the next render
    rebuilds from the mutated vertices."""
    drawable._np_rest_vertices = None   # noqa: SLF001 — runtime's private cache


def move_vertex(
    drawable: Drawable, index: int, x: float, y: float,
) -> bool:
    """Move ``drawable.vertices[index]`` to ``(x, y)``. Returns
    ``True`` on success, ``False`` if the index is out of range."""
    if index < 0 or index >= len(drawable.vertices):
        return False
    drawable.vertices[index] = (float(x), float(y))
    _invalidate_rest_cache(drawable)
    return True


def delete_vertex(drawable: Drawable, index: int) -> bool:
    """Remove a vertex and every triangle that referenced it. Adjusts
    indices > ``index`` in the index array down by one. UV array stays
    aligned with vertices.

    Returns ``True`` if the vertex was removed. The drawable's bone weights
    and vertex-morph deltas lose the same entry, so they stay aligned."""
    if index < 0 or index >= len(drawable.vertices):
        return False
    remap_vertex_data(drawable, [i for i in range(len(drawable.vertices)) if i != index])
    drawable.vertices.pop(index)
    if index < len(drawable.uvs):
        drawable.uvs.pop(index)
    # Drop any triangle that used this vertex; shift remaining indices.
    new_indices: list[int] = []
    for tri_start in range(0, len(drawable.indices), 3):
        tri = drawable.indices[tri_start:tri_start + 3]
        if len(tri) != 3:
            continue
        if index in tri:
            continue
        new_indices.extend(i - 1 if i > index else i for i in tri)
    drawable.indices = new_indices
    _invalidate_rest_cache(drawable)
    return True


def find_drawable_at(
    document: PuppetDocument, x: float, y: float, *, radius: float = 8.0,
) -> tuple[str, int] | None:
    """Search every drawable for a vertex near ``(x, y)``. Returns
    ``(drawable_id, vertex_index)`` for the topmost (highest
    draw_order) hit, or ``None``."""
    candidates = sorted(
        document.drawables, key=lambda d: -d.draw_order,
    )
    for drawable in candidates:
        idx = find_vertex_at(drawable, x, y, radius=radius)
        if idx is not None:
            return (drawable.id, idx)
    return None


def remap_vertex_data(drawable: Drawable, sources: Sequence[int]) -> None:
    """Re-index *drawable*'s per-vertex data: new vertex ``n`` takes what ``sources[n]`` had.

    Covers every ``bone_weights`` list and both delta lists of each
    ``vertex_morphs`` entry (an index past a short list reads as zero), and
    drops runtime's cached arrays of the old deltas. The caller replaces
    ``vertices``, ``uvs`` and ``indices`` itself.
    """
    if drawable.bone_weights:
        drawable.bone_weights = {
            bone: [float(weights[i]) if i < len(weights) else 0.0 for i in sources]
            for bone, weights in drawable.bone_weights.items()
        }
    if drawable.vertex_morphs:
        drawable.vertex_morphs = [_remap_morph(morph, sources) for morph in drawable.vertex_morphs]


def _remap_morph(morph: dict, sources: Sequence[int]) -> dict:
    out = {key: value for key, value in morph.items() if not key.startswith("_np_")}
    for side in _MORPH_SIDES:
        deltas = morph.get(side)
        if deltas is not None:
            out[side] = [
                tuple(float(c) for c in deltas[i]) if i < len(deltas) else (0.0, 0.0)
                for i in sources
            ]
    return out
