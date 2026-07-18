"""A mesh edit must invalidate runtime's memoised rest-vertex cache.

runtime._rest_vertices_array caches drawable._np_rest_vertices and never
invalidated it, so a vertex move/delete was composed from the stale cache and
stayed invisible on a parameterised rig.
"""
from __future__ import annotations

from Imervue.puppet.document import Drawable
from Imervue.puppet.mesh_edit import delete_vertex, move_vertex
from Imervue.puppet.runtime import _rest_vertices_array


def _drawable(vertices):
    return Drawable(
        id="face", texture="x.png", vertices=list(vertices),
        indices=[0, 1, 2], uvs=[(0.0, 0.0)] * len(vertices), draw_order=0,
    )


def test_move_vertex_invalidates_the_cache():
    d = _drawable([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
    assert _rest_vertices_array(d).tolist()[1] == [1.0, 1.0]   # cache built
    assert move_vertex(d, 1, 5.0, 6.0) is True
    assert _rest_vertices_array(d).tolist()[1] == [5.0, 6.0]   # rebuilt, moved


def test_delete_vertex_invalidates_the_cache():
    d = _drawable([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
    assert len(_rest_vertices_array(d)) == 3   # cache built
    assert delete_vertex(d, 1) is True
    assert len(_rest_vertices_array(d)) == 2   # rebuilt to the shorter list
