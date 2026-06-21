"""Repair topology problems in a puppet drawable's ``(vertices, indices, uvs)``.

A hand-edited or imported mesh accumulates the usual corruptions: triangles
with a repeated or out-of-range corner, zero-area (degenerate) triangles,
coincident duplicate vertices, and vertices no triangle references any more.
:func:`repair_mesh` runs the full clean-up in one pass and returns the fixed
mesh plus a :class:`MeshReport` of what it changed; the ``find_*`` detectors
expose each check on its own for diagnostics. Pure geometry — no Qt, no numpy.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

Vertex = tuple[float, float]


@dataclass
class MeshReport:
    """Tally of the edits :func:`repair_mesh` made."""

    removed_degenerate: int = 0
    dropped_out_of_range: int = 0
    merged_vertices: int = 0
    removed_unreferenced: int = 0

    @property
    def changed(self) -> bool:
        """True when the repair altered the mesh at all."""
        return bool(
            self.removed_degenerate
            or self.dropped_out_of_range
            or self.merged_vertices
            or self.removed_unreferenced,
        )


@dataclass
class RepairedMesh:
    """A cleaned mesh plus the :class:`MeshReport` describing the clean-up."""

    vertices: list[Vertex]
    indices: list[int]
    uvs: list[Vertex]
    report: MeshReport


def triangle_area(a: Vertex, b: Vertex, c: Vertex) -> float:
    """Return the (unsigned) area of triangle ``a, b, c``."""
    return 0.5 * abs(
        (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]),
    )


def _triangles(indices: Sequence[int]) -> list[tuple[int, int, int]]:
    usable = len(indices) - len(indices) % 3
    return [tuple(indices[i : i + 3]) for i in range(0, usable, 3)]  # type: ignore[misc]


def find_out_of_range_triangles(
    vertex_count: int, indices: Sequence[int],
) -> list[int]:
    """Return ordinals of triangles referencing an index outside ``[0, n)``."""
    return [
        n
        for n, tri in enumerate(_triangles(indices))
        if any(not 0 <= idx < vertex_count for idx in tri)
    ]


def find_degenerate_triangles(
    vertices: Sequence[Vertex], indices: Sequence[int], *, area_eps: float = 0.0,
) -> list[int]:
    """Return ordinals of triangles that are degenerate.

    A triangle is degenerate when two corners share an index, or when its
    area is ``<= area_eps`` (collinear / coincident corners). Triangles with an
    out-of-range index are skipped here — see :func:`find_out_of_range_triangles`.
    """
    out: list[int] = []
    count = len(vertices)
    for n, (i, j, k) in enumerate(_triangles(indices)):
        if any(not 0 <= idx < count for idx in (i, j, k)):
            continue
        if len({i, j, k}) < 3 or (
            triangle_area(vertices[i], vertices[j], vertices[k]) <= area_eps
        ):
            out.append(n)
    return out


def find_duplicate_vertices(
    vertices: Sequence[Vertex], *, tol: float = 0.0,
) -> dict[int, int]:
    """Map each duplicate vertex index to the earliest index at its position.

    With ``tol == 0`` positions must match exactly; ``tol > 0`` folds any
    vertex within Chebyshev distance ``tol`` of an earlier one.
    """
    remap = _build_remap(vertices, tol)
    return {dup: canon for dup, canon in remap.items() if dup != canon}


def find_unreferenced_vertices(
    vertex_count: int, indices: Sequence[int],
) -> list[int]:
    """Return indices in ``[0, n)`` that no in-range triangle references."""
    used = {idx for idx in indices if 0 <= idx < vertex_count}
    return [i for i in range(vertex_count) if i not in used]


def repair_mesh(
    vertices: Sequence[Vertex],
    indices: Sequence[int],
    uvs: Sequence[Vertex],
    *,
    merge_tol: float = 0.0,
    area_eps: float = 0.0,
) -> RepairedMesh:
    """Clean a mesh's topology and report what changed.

    The pass, in order: drop triangles with an out-of-range index, fold
    duplicate vertices (within ``merge_tol``) onto a canonical corner, drop
    degenerate triangles (``area <= area_eps``), then compact away every vertex
    no surviving triangle references and reindex.

    Raises :class:`ValueError` when ``uvs`` and ``vertices`` differ in length.
    """
    verts = [(float(x), float(y)) for x, y in vertices]
    uv_list = [(float(u), float(v)) for u, v in uvs]
    if len(uv_list) != len(verts):
        raise ValueError(
            f"uvs ({len(uv_list)}) and vertices ({len(verts)}) length mismatch",
        )
    report = MeshReport()
    tris = _drop_out_of_range(_triangles(indices), len(verts), report)
    remap = _build_remap(verts, merge_tol)
    report.merged_vertices = len(verts) - len({*remap.values()})
    tris = _apply_remap_drop_degenerate(tris, remap, verts, area_eps, report)
    return _compact(verts, uv_list, tris, remap, report)


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def _drop_out_of_range(
    tris: list[tuple[int, int, int]], count: int, report: MeshReport,
) -> list[tuple[int, int, int]]:
    kept: list[tuple[int, int, int]] = []
    for tri in tris:
        if all(0 <= idx < count for idx in tri):
            kept.append(tri)
        else:
            report.dropped_out_of_range += 1
    return kept


def _apply_remap_drop_degenerate(
    tris: list[tuple[int, int, int]],
    remap: dict[int, int],
    verts: list[Vertex],
    area_eps: float,
    report: MeshReport,
) -> list[tuple[int, int, int]]:
    kept: list[tuple[int, int, int]] = []
    for tri in tris:
        i, j, k = (remap[idx] for idx in tri)
        degenerate = len({i, j, k}) < 3 or (
            triangle_area(verts[i], verts[j], verts[k]) <= area_eps
        )
        if degenerate:
            report.removed_degenerate += 1
        else:
            kept.append((i, j, k))
    return kept


def _compact(
    verts: list[Vertex],
    uv_list: list[Vertex],
    tris: list[tuple[int, int, int]],
    remap: dict[int, int],
    report: MeshReport,
) -> RepairedMesh:
    referenced = sorted({idx for tri in tris for idx in tri})
    report.removed_unreferenced = len({*remap.values()}) - len(referenced)
    relabel = {old: new for new, old in enumerate(referenced)}
    new_vertices = [verts[i] for i in referenced]
    new_uvs = [uv_list[i] for i in referenced]
    new_indices = [relabel[idx] for tri in tris for idx in tri]
    return RepairedMesh(new_vertices, new_indices, new_uvs, report)


def _build_remap(vertices: Sequence[Vertex], tol: float) -> dict[int, int]:
    if tol <= 0:
        return _build_remap_exact(vertices)
    return _build_remap_tol(vertices, tol)


def _build_remap_exact(vertices: Sequence[Vertex]) -> dict[int, int]:
    seen: dict[Vertex, int] = {}
    remap: dict[int, int] = {}
    for i, vert in enumerate(vertices):
        key = (vert[0], vert[1])
        remap[i] = seen.setdefault(key, i)
    return remap


def _build_remap_tol(vertices: Sequence[Vertex], tol: float) -> dict[int, int]:
    canon: list[int] = []
    remap: dict[int, int] = {}
    for i, vert in enumerate(vertices):
        match = next(
            (
                c
                for c in canon
                if abs(vertices[c][0] - vert[0]) <= tol
                and abs(vertices[c][1] - vert[1]) <= tol
            ),
            None,
        )
        if match is None:
            canon.append(i)
            remap[i] = i
        else:
            remap[i] = match
    return remap
