"""Tests for puppet mesh topology repair."""
from __future__ import annotations

import pytest

from Imervue.puppet.mesh_repair import (
    find_degenerate_triangles,
    find_duplicate_vertices,
    find_out_of_range_triangles,
    find_unreferenced_vertices,
    repair_mesh,
    triangle_area,
)


def _unit_quad():
    # Two triangles forming a 1x1 quad, with matching uvs.
    vertices = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    indices = [0, 1, 2, 0, 2, 3]
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    return vertices, indices, uvs


# ---------------------------------------------------------------------------
# triangle_area
# ---------------------------------------------------------------------------


def test_triangle_area_right_triangle():
    assert triangle_area((0, 0), (2, 0), (0, 2)) == 2.0


def test_collinear_triangle_has_zero_area():
    assert triangle_area((0, 0), (1, 1), (2, 2)) == 0.0


# ---------------------------------------------------------------------------
# detectors
# ---------------------------------------------------------------------------


def test_find_out_of_range_triangles():
    verts = [(0, 0), (1, 0), (1, 1)]
    indices = [0, 1, 2, 0, 1, 9]
    assert find_out_of_range_triangles(len(verts), indices) == [1]


def test_find_degenerate_by_repeated_index():
    verts = [(0, 0), (1, 0), (1, 1)]
    assert find_degenerate_triangles(verts, [0, 1, 1]) == [0]


def test_find_degenerate_by_zero_area():
    verts = [(0, 0), (1, 1), (2, 2)]  # collinear
    assert find_degenerate_triangles(verts, [0, 1, 2]) == [0]


def test_find_degenerate_skips_out_of_range():
    verts = [(0, 0), (1, 0)]
    # index 5 is out of range — not counted as degenerate here.
    assert find_degenerate_triangles(verts, [0, 1, 5]) == []


def test_find_duplicate_vertices_exact():
    verts = [(0, 0), (1, 0), (0, 0), (1, 0)]
    assert find_duplicate_vertices(verts) == {2: 0, 3: 1}


def test_find_duplicate_vertices_tolerance():
    verts = [(0.0, 0.0), (0.4, 0.0), (5.0, 5.0)]
    assert find_duplicate_vertices(verts, tol=0.5) == {1: 0}
    assert find_duplicate_vertices(verts, tol=0.0) == {}


def test_find_unreferenced_vertices():
    verts = [(0, 0), (1, 0), (1, 1), (9, 9)]
    indices = [0, 1, 2]
    assert find_unreferenced_vertices(len(verts), indices) == [3]


# ---------------------------------------------------------------------------
# repair_mesh
# ---------------------------------------------------------------------------


def test_repair_clean_mesh_is_unchanged():
    verts, indices, uvs = _unit_quad()
    result = repair_mesh(verts, indices, uvs)
    assert result.vertices == verts
    assert result.indices == indices
    assert result.uvs == uvs
    assert result.report.changed is False


def test_repair_drops_out_of_range_triangle():
    verts, indices, uvs = _unit_quad()
    indices = [*indices, 0, 2, 99]
    result = repair_mesh(verts, indices, uvs)
    assert result.report.dropped_out_of_range == 1
    assert result.indices == [0, 1, 2, 0, 2, 3]


def test_repair_drops_degenerate_triangle():
    verts, indices, uvs = _unit_quad()
    indices = [*indices, 0, 1, 1]  # repeated corner
    result = repair_mesh(verts, indices, uvs)
    assert result.report.removed_degenerate == 1
    assert len(result.indices) == 6


def test_repair_merges_duplicate_vertices_and_reindexes():
    # Vertex 4 duplicates vertex 2's position; the second triangle uses it.
    verts = [(0, 0), (1, 0), (1, 1), (0, 1), (1, 1)]
    indices = [0, 1, 2, 0, 4, 3]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 1), (1, 1)]
    result = repair_mesh(verts, indices, uvs)
    assert result.report.merged_vertices == 1
    assert len(result.vertices) == 4
    # Both triangles survive, now sharing the merged corner.
    assert len(result.indices) == 6


def test_repair_removes_unreferenced_vertex_and_compacts():
    verts, indices, uvs = _unit_quad()
    verts = [*verts, (9.0, 9.0)]  # stray, unreferenced
    uvs = [*uvs, (0.9, 0.9)]
    result = repair_mesh(verts, indices, uvs)
    assert result.report.removed_unreferenced == 1
    assert len(result.vertices) == 4
    assert (9.0, 9.0) not in result.vertices


def test_repair_handles_collinear_zero_area_via_eps():
    verts = [(0, 0), (1, 1), (2, 2)]
    uvs = [(0, 0), (0.5, 0.5), (1, 1)]
    result = repair_mesh(verts, [0, 1, 2], uvs)
    assert result.report.removed_degenerate == 1
    assert result.indices == []
    assert result.vertices == []


def test_repair_truncates_trailing_partial_triangle():
    verts, indices, uvs = _unit_quad()
    indices = [*indices, 0, 1]  # two stray indices, not a full triangle
    result = repair_mesh(verts, indices, uvs)
    assert result.indices == [0, 1, 2, 0, 2, 3]


def test_repair_uv_length_mismatch_raises():
    verts, indices, _ = _unit_quad()
    with pytest.raises(ValueError, match="length mismatch"):
        repair_mesh(verts, indices, [(0, 0)])


def test_repair_report_counts_sum_to_vertex_reduction():
    verts = [(0, 0), (1, 0), (1, 1), (0, 0), (5, 5)]  # dup of 0, plus stray
    indices = [0, 1, 2, 3, 1, 2]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 0), (0.5, 0.5)]
    result = repair_mesh(verts, indices, uvs)
    removed = result.report.merged_vertices + result.report.removed_unreferenced
    assert removed == len(verts) - len(result.vertices)
