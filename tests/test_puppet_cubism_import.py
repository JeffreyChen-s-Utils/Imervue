"""Tests for the Cubism v3 JSON importers.

Each test synthesises its own ``.motion3.json`` / ``.exp3.json`` /
``.model3.json`` via ``json.dumps`` on ``tmp_path`` so the suite has
no checked-in binary fixtures.
"""
from __future__ import annotations

import json

import pytest

from puppet.cubism_import import (
    CubismFormatError,
    apply_bundle,
    load_exp3,
    load_model3,
    load_motion3,
)
from puppet.document import PuppetDocument


# ---------------------------------------------------------------------------
# .motion3.json
# ---------------------------------------------------------------------------


def _write_motion3(
    path,
    *,
    duration: float = 1.0,
    loop: bool = False,
    fade_in: float = 0.5,
    fade_out: float = 0.3,
    curves: list | None = None,
) -> None:
    payload = {
        "Version": 3,
        "Meta": {
            "Duration": duration,
            "Fps": 30,
            "Loop": loop,
            "FadeInTime": fade_in,
            "FadeOutTime": fade_out,
        },
        "Curves": curves if curves is not None else [
            {
                "Target": "Parameter",
                "Id": "ParamAngleX",
                "Segments": [0.0, 0.0,   0, 0.5, 0.5,   0, 1.0, 1.0],
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_motion3_parses_meta(tmp_path):
    p = tmp_path / "idle.motion3.json"
    _write_motion3(p)
    motion = load_motion3(p)
    assert motion.name == "idle"
    assert motion.duration == pytest.approx(1.0)
    assert motion.fade_in_duration == pytest.approx(0.5)
    assert motion.fade_out_duration == pytest.approx(0.3)


def test_load_motion3_translates_linear_segments(tmp_path):
    p = tmp_path / "linear.motion3.json"
    _write_motion3(p)
    motion = load_motion3(p)
    assert len(motion.tracks) == 1
    segments = motion.tracks[0].segments
    assert all(s.type == "linear" for s in segments)
    assert segments[0].p0 == (0.0, 0.0)
    assert segments[0].p1 == (0.5, 0.5)
    assert segments[1].p1 == (1.0, 1.0)


def test_load_motion3_translates_bezier_segments(tmp_path):
    p = tmp_path / "bezier.motion3.json"
    curves = [
        {
            "Target": "Parameter",
            "Id": "ParamAngleY",
            # [t0, v0, type=1, c0_t, c0_v, c1_t, c1_v, p1_t, p1_v]
            "Segments": [0.0, 0.0,   1, 0.1, 0.3, 0.4, 0.7, 0.5, 1.0],
        },
    ]
    _write_motion3(p, curves=curves)
    motion = load_motion3(p)
    seg = motion.tracks[0].segments[0]
    assert seg.type == "cubic-bezier"
    assert seg.p0 == (0.0, 0.0)
    assert seg.p1 == (0.5, 1.0)
    assert seg.c0 == (0.1, 0.3)
    assert seg.c1 == (0.4, 0.7)


def test_load_motion3_translates_stepped_and_inverse_stepped(tmp_path):
    p = tmp_path / "stepped.motion3.json"
    curves = [
        {
            "Target": "Parameter",
            "Id": "ParamAngleZ",
            "Segments": [0.0, 0.0,   2, 0.5, 1.0,   3, 1.0, 0.5],
        },
    ]
    _write_motion3(p, curves=curves)
    motion = load_motion3(p)
    types = [s.type for s in motion.tracks[0].segments]
    assert types == ["stepped", "inverse-stepped"]


def test_load_motion3_skips_non_parameter_curves(tmp_path):
    p = tmp_path / "mixed.motion3.json"
    curves = [
        {
            "Target": "Parameter",
            "Id": "ParamAngleX",
            "Segments": [0.0, 0.0,   0, 1.0, 1.0],
        },
        {
            "Target": "PartOpacity",
            "Id": "PartArtMesh1",
            "Segments": [0.0, 1.0,   0, 1.0, 0.0],
        },
        {
            "Target": "Model",
            "Id": "Opacity",
            "Segments": [0.0, 1.0,   0, 1.0, 0.0],
        },
    ]
    _write_motion3(p, curves=curves)
    motion = load_motion3(p)
    assert [t.param_id for t in motion.tracks] == ["ParamAngleX"]


def test_load_motion3_unknown_segment_type_raises(tmp_path):
    p = tmp_path / "bad.motion3.json"
    curves = [
        {
            "Target": "Parameter",
            "Id": "X",
            "Segments": [0.0, 0.0,   99, 1.0, 1.0],
        },
    ]
    _write_motion3(p, curves=curves)
    with pytest.raises(CubismFormatError):
        load_motion3(p)


# ---------------------------------------------------------------------------
# .exp3.json
# ---------------------------------------------------------------------------


def test_load_exp3_maps_blend_modes(tmp_path):
    p = tmp_path / "smile.exp3.json"
    p.write_text(json.dumps({
        "Type": "Live2D Expression",
        "Parameters": [
            {"Id": "ParamMouthForm", "Value": 1.0, "Blend": "Add"},
            {"Id": "ParamEyeLOpen", "Value": 0.0, "Blend": "Multiply"},
            {"Id": "ParamEyeBallX", "Value": 0.5, "Blend": "Overwrite"},
        ],
    }), encoding="utf-8")
    expr = load_exp3(p)
    assert expr.name == "smile"
    modes = {pp.id: pp.mode for pp in expr.params}
    assert modes == {
        "ParamMouthForm": "additive",
        "ParamEyeLOpen": "multiply",
        "ParamEyeBallX": "overwrite",
    }


def test_load_exp3_unknown_blend_mode_raises(tmp_path):
    p = tmp_path / "broken.exp3.json"
    p.write_text(json.dumps({
        "Type": "Live2D Expression",
        "Parameters": [{"Id": "X", "Value": 1.0, "Blend": "Wat"}],
    }), encoding="utf-8")
    with pytest.raises(CubismFormatError):
        load_exp3(p)


def test_load_exp3_wrong_type_field_raises(tmp_path):
    p = tmp_path / "weird.exp3.json"
    p.write_text(json.dumps({
        "Type": "NotALive2DFile",
        "Parameters": [],
    }), encoding="utf-8")
    with pytest.raises(CubismFormatError):
        load_exp3(p)


# ---------------------------------------------------------------------------
# .model3.json
# ---------------------------------------------------------------------------


def _write_minimal_motion3(path, *, param_id: str = "ParamAngleX") -> None:
    path.write_text(json.dumps({
        "Version": 3,
        "Meta": {"Duration": 1.0, "Fps": 30, "Loop": False},
        "Curves": [
            {
                "Target": "Parameter",
                "Id": param_id,
                "Segments": [0.0, 0.0,   0, 1.0, 1.0],
            },
        ],
    }), encoding="utf-8")


def _write_minimal_exp3(path, *, param_id: str = "ParamMouthForm") -> None:
    path.write_text(json.dumps({
        "Type": "Live2D Expression",
        "Parameters": [{"Id": param_id, "Value": 0.5, "Blend": "Add"}],
    }), encoding="utf-8")


def test_load_model3_resolves_referenced_files(tmp_path):
    motion_path = tmp_path / "motions" / "idle.motion3.json"
    motion_path.parent.mkdir()
    _write_minimal_motion3(motion_path)
    expr_path = tmp_path / "expressions" / "smile.exp3.json"
    expr_path.parent.mkdir()
    _write_minimal_exp3(expr_path)
    model_path = tmp_path / "model.model3.json"
    model_path.write_text(json.dumps({
        "Version": 3,
        "FileReferences": {
            "Motions": {
                "Idle": [
                    {"File": "motions/idle.motion3.json",
                     "FadeInTime": 0.4, "FadeOutTime": 0.7},
                ],
            },
            "Expressions": [{"Name": "smile", "File": "expressions/smile.exp3.json"}],
        },
        "Groups": [
            {"Target": "Parameter", "Name": "EyeBlink",
             "Ids": ["ParamEyeLOpen", "ParamEyeROpen"]},
            {"Target": "Parameter", "Name": "LipSync",
             "Ids": ["ParamMouthOpenY"]},
        ],
        "HitAreas": [{"Id": "ArtMesh_head", "Name": "Head"}],
    }), encoding="utf-8")
    bundle = load_model3(model_path)
    assert len(bundle.motions) == 1
    # Real file stem prefixed with group → "Idle/idle"
    assert bundle.motions[0].name == "Idle/idle"
    assert bundle.motions[0].group == "Idle"
    # FadeInTime on the model3 reference must override the motion3 file value.
    assert bundle.motions[0].fade_in_duration == pytest.approx(0.4)
    assert bundle.motions[0].fade_out_duration == pytest.approx(0.7)
    assert [e.name for e in bundle.expressions] == ["smile"]
    assert bundle.parameter_groups["EyeBlink"] == ["ParamEyeLOpen", "ParamEyeROpen"]
    assert [h.id for h in bundle.hit_areas] == ["Head"]


def test_apply_bundle_dedupes_by_name(tmp_path):
    from puppet.cubism_import import CubismBundle
    motion_path = tmp_path / "idle.motion3.json"
    _write_minimal_motion3(motion_path)
    doc = PuppetDocument(size=(64, 64))
    bundle = CubismBundle(motions=[load_motion3(motion_path, name="motion_a")])
    apply_bundle(doc, bundle)
    apply_bundle(doc, bundle)
    assert len(doc.motions) == 1


def test_load_motion3_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_motion3("does/not/exist.motion3.json")
