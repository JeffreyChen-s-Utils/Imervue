"""Puppet's Tools > Repair Rig fixes meshes and weight maps; deleting a vertex keeps data aligned.

``puppet/mesh_repair.py`` and ``puppet/bone_weights.py`` were tested but
unreachable. ``rig_repair.repair_rig`` runs both over every drawable, carrying
bone weights and vertex-morph deltas across the re-indexed vertices — the same
remap ``mesh_edit.delete_vertex`` now applies (it used to leave them one entry
off after the deleted vertex).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.puppet.document import Drawable, PuppetDocument
from Imervue.puppet.mesh_edit import delete_vertex, remap_vertex_data
from Imervue.puppet.mesh_repair import repair_mesh
from Imervue.puppet.rig_repair import repair_rig
from Imervue.puppet.workspace import PuppetWorkspace

_SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
_SQUARE_UV = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def _drawable(**extra) -> Drawable:
    return Drawable(id="d", texture="t", vertices=list(_SQUARE), indices=[0, 1, 2, 0, 2, 3],
                    uvs=list(_SQUARE_UV), **extra)


def test_remap_follows_the_sources_and_drops_cached_arrays():
    d = _drawable(bone_weights={"b": [0.1, 0.2, 0.3]},
                  vertex_morphs=[{"parameter": "P", "delta_at_min": [(1, 1), (2, 2), (3, 3), (4, 4)],
                                  "delta_at_max": [[5, 5], [6, 6], [7, 7], [8, 8]],
                                  "_np_delta_at_min": object()}])
    remap_vertex_data(d, [3, 0, 2])
    assert d.bone_weights == {"b": [0.0, 0.1, 0.3]}            # index 3 was past the short list
    (morph,) = d.vertex_morphs
    assert morph["delta_at_min"] == [(4.0, 4.0), (1.0, 1.0), (3.0, 3.0)]
    assert morph["delta_at_max"] == [(8.0, 8.0), (5.0, 5.0), (7.0, 7.0)]
    assert morph["parameter"] == "P" and "_np_delta_at_min" not in morph


def test_deleting_a_vertex_drops_its_weights_and_deltas():
    d = _drawable(bone_weights={"b": [0.1, 0.2, 0.3, 0.4]},
                  vertex_morphs=[{"parameter": "P", "delta_at_min": [(1, 0), (2, 0), (3, 0), (4, 0)]}])
    assert delete_vertex(d, 1) is True
    assert d.bone_weights == {"b": [0.1, 0.3, 0.4]}
    assert [x for x, _ in d.vertex_morphs[0]["delta_at_min"]] == [1.0, 3.0, 4.0]
    assert len(d.vertices) == len(d.uvs) == 3
    assert d.indices == [0, 1, 2]


def test_a_texture_seam_stays_split_only_when_uvs_must_match():
    verts = [*_SQUARE, (10.0, 0.0)]                       # vertex 4 sits on vertex 1 ...
    uvs = [*_SQUARE_UV, (0.5, 0.0)]                       # ... with a different UV
    indices = [0, 4, 2, 0, 2, 3]
    seam = repair_mesh(verts, indices, uvs, match_uvs=True)
    assert seam.report.merged_vertices == 0
    merged = repair_mesh(verts, indices, uvs)
    assert merged.report.merged_vertices == 1


def test_sources_name_the_input_vertex_of_each_output_vertex():
    verts = [(50.0, 50.0), *_SQUARE]                      # vertex 0 is used by nothing
    fixed = repair_mesh(verts, [1, 2, 3, 1, 3, 4], [(0.0, 0.0), *_SQUARE_UV])
    assert fixed.sources == [1, 2, 3, 4]
    assert fixed.vertices == _SQUARE


def test_repair_rig_fixes_mesh_and_weights_together():
    d = Drawable(
        id="d", texture="t",
        vertices=[*_SQUARE, (0.0, 0.0), (99.0, 99.0)],     # 4 duplicates 0; 5 is unused
        indices=[4, 1, 2, 0, 2, 3, 0, 0, 1],                # last triangle is degenerate
        uvs=[*_SQUARE_UV, (0.0, 0.0), (0.5, 0.5)],
        bone_weights={"a": [1.0, 0.5, 0.0, 2.0, 1.0, 1.0], "b": [0.0, 0.5, 0.0, 2.0, 0.0, 0.0]},
    )
    sound = _drawable()
    report = repair_rig(PuppetDocument(drawables=[d, sound]))
    assert report.changed and report.drawables == 1
    assert (report.merged_vertices, report.removed_unreferenced, report.removed_degenerate) == (1, 1, 1)
    assert report.weights_normalised == 1
    assert d.vertices == _SQUARE and d.indices == [0, 1, 2, 0, 2, 3]
    assert d.bone_weights == {"a": [1.0, 0.5, 0.0, 0.5], "b": [0.0, 0.5, 0.0, 0.5]}
    assert sound.vertices == _SQUARE


def test_a_sound_rig_reports_nothing():
    assert repair_rig(PuppetDocument(drawables=[_drawable()])).changed is False


def test_mismatched_uvs_skip_the_mesh_but_not_the_weights():
    d = _drawable(bone_weights={"a": [2.0, 2.0, 2.0, 2.0]})
    d.uvs = d.uvs[:2]
    report = repair_rig(PuppetDocument(drawables=[d]))
    assert report.weights_normalised == 1 and report.merged_vertices == 0
    assert d.bone_weights == {"a": [1.0, 1.0, 1.0, 1.0]}


def _host(document):
    said, loaded = [], []
    canvas = SimpleNamespace(document=lambda: document, load_document=loaded.append)
    host = SimpleNamespace(_canvas=canvas, _announce=lambda key, fallback, **fmt: said.append((key, fmt)))
    return host, said, loaded


@pytest.mark.parametrize(("document", "key"), [
    (None, "puppet_repair_rig_no_doc"),
    (PuppetDocument(drawables=[_drawable()]), "puppet_repair_rig_none"),
])
def test_the_menu_handler_says_when_there_is_nothing_to_do(document, key):
    host, said, loaded = _host(document)
    PuppetWorkspace._run_rig_repair(host)
    assert [k for k, _ in said] == [key] and loaded == []


def test_the_menu_handler_reloads_the_repaired_rig_and_reports_counts():
    d = _drawable(bone_weights={"a": [3.0, 3.0, 3.0, 3.0]})
    doc = PuppetDocument(drawables=[d])
    host, said, loaded = _host(doc)
    PuppetWorkspace._run_rig_repair(host)
    assert loaded == [doc]
    ((key, fmt),) = said
    assert key == "puppet_repair_rig_done"
    assert fmt["drawables"] == 1 and fmt["weights"] == 1 and fmt["merged"] == 0
