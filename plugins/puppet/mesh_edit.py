"""Pure-Python mesh-edit operations on a :class:`Drawable`.

The canvas's mesh-edit tool calls into here when the user clicks /
drags vertices. Every function returns a new vertex index (or
``None``) so the caller can keep selection state outside the document.
Qt-free; the actual mouse handling lives in the canvas widget.
"""
from __future__ import annotations

from puppet.document import Drawable, PuppetDocument


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


def move_vertex(
    drawable: Drawable, index: int, x: float, y: float,
) -> bool:
    """Move ``drawable.vertices[index]`` to ``(x, y)``. Returns
    ``True`` on success, ``False`` if the index is out of range."""
    if index < 0 or index >= len(drawable.vertices):
        return False
    drawable.vertices[index] = (float(x), float(y))
    return True


def delete_vertex(drawable: Drawable, index: int) -> bool:
    """Remove a vertex and every triangle that referenced it. Adjusts
    indices > ``index`` in the index array down by one. UV array stays
    aligned with vertices.

    Returns ``True`` if the vertex was removed."""
    if index < 0 or index >= len(drawable.vertices):
        return False
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
