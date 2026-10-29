"""Contract tests pinning the auto-rigger's full output.

Each scenario serialises the rigged :class:`PuppetDocument` with
``dataclasses.asdict`` and compares a SHA-256 of the canonical JSON
against a golden digest, so any change to ids, ordering, curve values,
deformer forms or parameter keys shows up. Explicit assertions next to
the digests document the edge cases they cover.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math

import pytest

from Imervue.puppet.auto_rig import auto_rig
from Imervue.puppet.document import (
    Deformer,
    Drawable,
    Parameter,
    ParameterKey,
    PhysicsRig,
    PuppetDocument,
)
from Imervue.puppet.standard_params import standard_parameters

_FULL_FACE = (
    "eye_l_open", "eye_l_close", "EyeROpen", "EyeRClosed",
    "mouth_open", "mouth_close", "mouth_a", "mouth_ii", "lip_u",
    "mouth_e", "mouth_open_o", "Head", "face_base", "forehead",
    "hair_front", "bangs", "Fringe-Left", "body",
)


def _quad(i: int) -> list[tuple[float, float]]:
    x = 10.0 + i * 20.0
    y = 5.0 + i * 7.0
    return [(x, y), (x + 10, y), (x + 10, y + 13), (x, y + 13)]


def _doc(ids: tuple[str, ...], *, size=(200, 160), vertices=True) -> PuppetDocument:
    doc = PuppetDocument(size=size)
    for i, name in enumerate(ids):
        doc.drawables.append(Drawable(
            id=name, texture=f"textures/{name}.png",
            vertices=_quad(i) if vertices else [],
            indices=[0, 1, 2, 0, 2, 3],
            uvs=[(0, 0), (1, 0), (1, 1), (0, 1)],
        ))
    return doc


def _digest(doc: PuppetDocument) -> str:
    payload = json.dumps(dataclasses.asdict(doc), sort_keys=True, default=repr)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _seeded_doc() -> PuppetDocument:
    """Document with colliding ids, pre-existing keys and opacity curves."""
    doc = _doc(("head", "hair_01", "eye_r_open"))
    doc.parameters = standard_parameters()
    doc.deformers.extend([
        Deformer(id="head_tilt", type="rotation", parent=None, drawables=[], form={}),
        Deformer(id="hair_swing", type="warp", parent=None, drawables=[], form={}),
        Deformer(id="hair_swing_2", type="warp", parent=None, drawables=[], form={}),
    ])
    doc.physics_rigs.append(PhysicsRig(id="hair_chain", input_param="a", output_param="b"))
    z = doc.parameter("ParamAngleZ")
    z.keys = [
        ParameterKey(value=0.5, forms={"other": {"angle": 0.2}}),
        ParameterKey(value=1e-7, forms={"other": {"angle": 0.1}}),
    ]
    doc.drawable("eye_r_open").opacity_keys = [
        {"parameter": "Custom", "stops": [{"value": 0.0, "alpha": 0.5}]},
        {"parameter": "ParamEyeROpen", "stops": [{"value": 0.3, "alpha": 0.3}]},
    ]
    return doc


def test_full_face_document_is_pinned():
    doc = _doc(_FULL_FACE)
    counts = auto_rig(doc)
    assert counts == {"eyes": 4, "mouth": 7, "head_tilt": 2, "hair_swing": 3}
    assert [d.id for d in doc.deformers] == ["head_tilt", "hair_swing"]
    assert [p.id for p in doc.parameters] == ["ParamAngleZ", "ParamAngleX", "ParamHairFront"]
    assert _digest(doc) == "4b1e5be833416a2dc4062f1d8c4d938122483fbaaf51b207db9e034d6f677c93"


def test_full_face_with_standard_parameters_is_pinned():
    doc = _doc(_FULL_FACE)
    doc.parameters = standard_parameters()
    auto_rig(doc)
    assert _digest(doc) == "7ac27067de6dbdb9ae805689706fc27f7a2eea80298f53410cd0b60004af7ab7"


def test_no_matching_layers_leaves_document_untouched():
    doc = _doc(("body", "arm_left", "leg", "forehead"))
    before = _digest(doc)
    counts = auto_rig(doc)
    assert counts == {"eyes": 0, "mouth": 0, "head_tilt": 0, "hair_swing": 0}
    assert _digest(doc) == before


def test_hair_without_vertices_is_skipped_but_head_falls_back_to_canvas_centre():
    doc = _doc(("hair_01", "head"), size=(300, 120), vertices=False)
    counts = auto_rig(doc)
    assert counts["hair_swing"] == 0
    assert counts["head_tilt"] == 1
    assert [d.id for d in doc.deformers] == ["head_tilt"]
    assert doc.deformers[0].form == {"anchor": [150.0, 60.0], "angle": 0.0}
    assert [p.id for p in doc.parameters] == ["ParamAngleZ"]
    assert doc.physics_rigs == []
    assert _digest(doc) == "7b8f9b4f0872d7edc2d752e1328eb2031c2b1f89c704b74fc041b7582f369ce6"


def test_seeded_document_merges_keys_and_picks_unique_ids():
    doc = _seeded_doc()
    auto_rig(doc)
    assert [d.id for d in doc.deformers][3:] == ["head_tilt_2", "hair_swing_3"]
    assert [r.id for r in doc.physics_rigs] == ["hair_chain", "hair_chain_2"]
    z = doc.parameter("ParamAngleZ")
    assert [k.value for k in z.keys] == [-1.0, pytest.approx(1e-7), 0.5, 1.0]
    assert z.keys[1].forms == {"other": {"angle": 0.1}, "head_tilt_2": {"angle": 0.0}}
    assert z.keys[3].forms["head_tilt_2"]["angle"] == pytest.approx(math.radians(15.0))
    curves = doc.drawable("eye_r_open").opacity_keys
    assert curves == [
        {"parameter": "Custom", "stops": [{"value": 0.0, "alpha": 0.5}]},
        {"parameter": "ParamEyeROpen", "stops": [
            {"value": 0.0, "alpha": 0.0}, {"value": 1.0, "alpha": 1.0},
        ]},
    ]
    assert _digest(doc) == "79892b550957d4f8e651ade0ae504f0f7830e869c3597de6c0754beb3c62e134"


def test_seeded_document_second_pass_is_pinned():
    doc = _seeded_doc()
    auto_rig(doc)
    counts = auto_rig(doc)
    assert counts == {"eyes": 1, "mouth": 0, "head_tilt": 1, "hair_swing": 1}
    assert [d.id for d in doc.deformers][5:] == ["head_tilt_3", "hair_swing_4"]
    assert [r.id for r in doc.physics_rigs] == ["hair_chain", "hair_chain_2", "hair_chain_3"]
    assert _digest(doc) == "947553df74ae9768817e0ca6291aabddadf9d06632337512bcf238dc417eb56d"


def test_mouth_curves_are_exact():
    doc = _doc(("mouth_close", "mouth_i", "mouth_u", "mouth_e", "mouth_open"))
    auto_rig(doc)
    keys = {d.id: d.opacity_keys for d in doc.drawables}
    assert keys["mouth_close"] == [{"parameter": "ParamMouthOpenY", "stops": [
        {"value": 0.0, "alpha": 1.0}, {"value": 1.0, "alpha": 0.0},
    ]}]
    assert keys["mouth_open"] == [{"parameter": "ParamMouthOpenY", "stops": [
        {"value": 0.0, "alpha": 0.0}, {"value": 1.0, "alpha": 1.0},
    ]}]
    assert keys["mouth_i"][1]["stops"] == [
        {"value": -1.0, "alpha": 0.0}, {"value": 1.0, "alpha": 1.0},
        {"value": 1.0, "alpha": 1.0},
    ]
    assert keys["mouth_u"][1]["stops"] == [
        {"value": -1.0, "alpha": 1.0}, {"value": -1.0, "alpha": 1.0},
        {"value": 1.0, "alpha": 0.0},
    ]
    e_stops = keys["mouth_e"][1]["stops"]
    assert e_stops[0] == {"value": -1.0, "alpha": 0.0}
    assert e_stops[1] == {"value": 0.3, "alpha": 1.0}
    assert e_stops[2]["alpha"] == pytest.approx(0.3)


def test_existing_parameter_is_not_duplicated_or_reranged():
    doc = _doc(("head",))
    doc.parameters = [Parameter(id="ParamAngleZ", min=-30.0, max=30.0, default=0.0)]
    auto_rig(doc)
    assert len(doc.parameters) == 1
    assert (doc.parameters[0].min, doc.parameters[0].max) == (-30.0, 30.0)
    assert [k.value for k in doc.parameters[0].keys] == [-1.0, 0.0, 1.0]
