"""Puppet's **Tools > Repair Rig**: fix every drawable's mesh and bone-weight map in one pass.

Per drawable, :func:`~Imervue.puppet.mesh_repair.repair_mesh` drops broken and
zero-area triangles, merges duplicate vertices that share position *and* UV
(a texture seam stays split) and removes vertices no triangle uses; the bone
weights and vertex-morph deltas follow the surviving vertices. Then
:func:`~Imervue.puppet.bone_weights.normalize_drawable_weights` makes every
influenced vertex's weights sum to 1. Pure document work — no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass

from Imervue.puppet.bone_weights import normalize_drawable_weights
from Imervue.puppet.document import Drawable, PuppetDocument
from Imervue.puppet.mesh_edit import remap_vertex_data
from Imervue.puppet.mesh_repair import repair_mesh


@dataclass
class RigRepairReport:
    """What :func:`repair_rig` changed, summed over the rig."""

    drawables: int = 0
    removed_degenerate: int = 0
    dropped_out_of_range: int = 0
    merged_vertices: int = 0
    removed_unreferenced: int = 0
    weights_normalised: int = 0

    @property
    def changed(self) -> bool:
        """True when any drawable was altered."""
        return self.drawables > 0


def repair_rig(document: PuppetDocument) -> RigRepairReport:
    """Repair every drawable of *document* in place and report the totals."""
    report = RigRepairReport()
    for drawable in document.drawables:
        mesh_changed = _repair_drawable_mesh(drawable, report)
        weights_changed = normalize_drawable_weights(drawable)
        report.weights_normalised += int(weights_changed)
        report.drawables += int(mesh_changed or weights_changed)
    return report


def _repair_drawable_mesh(drawable: Drawable, report: RigRepairReport) -> bool:
    """Clean *drawable*'s topology; False when it was sound or its UVs don't line up."""
    if not drawable.vertices or len(drawable.uvs) != len(drawable.vertices):
        return False
    fixed = repair_mesh(drawable.vertices, drawable.indices, drawable.uvs, match_uvs=True)
    if not fixed.report.changed:
        return False
    remap_vertex_data(drawable, fixed.sources)
    drawable.vertices, drawable.indices, drawable.uvs = fixed.vertices, fixed.indices, fixed.uvs
    drawable._np_rest_vertices = None   # noqa: SLF001 — runtime's private cache
    report.removed_degenerate += fixed.report.removed_degenerate
    report.dropped_out_of_range += fixed.report.dropped_out_of_range
    report.merged_vertices += fixed.report.merged_vertices
    report.removed_unreferenced += fixed.report.removed_unreferenced
    return True
