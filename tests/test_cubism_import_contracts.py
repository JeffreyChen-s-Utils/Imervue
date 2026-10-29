"""Contract tests for the Cubism v3 JSON importers.

Pin the serialised form of every importer's output on small synthetic
bundles, the skipped malformed entries, and the exact error messages
for malformed input, so the importers can be reorganised without a
behaviour change.
"""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from Imervue.puppet import cubism_import
from Imervue.puppet.cubism_import import (
    CubismBundle,
    CubismFormatError,
    apply_bundle,
    load_cdi3,
    load_exp3,
    load_model3,
    load_motion3,
    load_physics3,
    load_pose3,
)
from Imervue.puppet.document import HitArea, Motion, PuppetDocument


def _write(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _segment(kind, p0, p1, c0=None, c1=None) -> dict:
    return {"type": kind, "p0": p0, "p1": p1, "c0": c0, "c1": c1}


_MOTION_RAW = {
    "Meta": {"Duration": 2, "Loop": True, "FadeInTime": 0.5, "FadeOutTime": 0.25},
    "Curves": [
        {"Target": "Model", "Id": "Opacity", "Segments": [0, 1, 0, 1, 1]},
        {"Target": "Parameter", "Id": 7, "Segments": [0, 0]},
        {"Target": "Parameter", "Id": "NoSegments"},
        {"Target": "Parameter", "Id": "Short", "Segments": [0]},
        {
            "Target": "Parameter", "Id": "ParamAngleX",
            "Segments": [
                0, 0,
                0, 1, 10,
                1, 1.2, 11, 1.4, 12, 1.5, 13,
                2, 1.8, 14,
                3, 2, 15,
            ],
        },
    ],
}

_EXPECTED_TRACKS = [
    {"param_id": "Short", "segments": []},
    {
        "param_id": "ParamAngleX",
        "segments": [
            _segment("linear", (0.0, 0.0), (1.0, 10.0)),
            _segment("cubic-bezier", (1.0, 10.0), (1.5, 13.0), (1.2, 11.0), (1.4, 12.0)),
            _segment("stepped", (1.5, 13.0), (1.8, 14.0)),
            _segment("inverse-stepped", (1.8, 14.0), (2.0, 15.0)),
        ],
    },
]


def _motion_dict(name, *, fade_in=0.5, fade_out=0.25, group=None, sound=None) -> dict:
    return {
        "name": name, "duration": 2.0, "loop": True, "tracks": _EXPECTED_TRACKS,
        "fade_in_duration": fade_in, "fade_out_duration": fade_out,
        "group": group, "sound_path": sound,
    }


def test_motion3_serialised_form(tmp_path):
    path = tmp_path / "idle_01.motion3.json"
    _write(path, _MOTION_RAW)
    motion = load_motion3(path)
    assert asdict(motion) == _motion_dict("idle_01")
    assert load_motion3(path, name="Custom").name == "Custom"


def test_motion3_without_meta_or_curves_defaults(tmp_path):
    path = tmp_path / "bare.motion3.json"
    _write(path, {})
    motion = load_motion3(path)
    assert (motion.duration, motion.loop, motion.tracks) == (0.0, False, [])
    assert (motion.fade_in_duration, motion.fade_out_duration) == (0.0, 0.0)


def test_motion3_unknown_segment_type_message(tmp_path):
    path = tmp_path / "bad.motion3.json"
    _write(path, {"Curves": [{"Target": "Parameter", "Id": "P", "Segments": [0, 0, 9, 1, 1]}]})
    with pytest.raises(CubismFormatError, match=r"^unknown Cubism segment type 9$"):
        load_motion3(path)


def test_motion3_truncated_segment_message(tmp_path):
    path = tmp_path / "cut.motion3.json"
    _write(path, {"Curves": [{"Target": "Parameter", "Id": "P", "Segments": [0, 0, 1, 1, 1]}]})
    with pytest.raises(CubismFormatError) as info:
        load_motion3(path)
    assert str(info.value) == (
        "truncated Cubism motion: segment type 1 needs 6 floats at 3, only 5 present"
    )


def test_malformed_json_message_and_missing_file(tmp_path):
    path = tmp_path / "broken.exp3.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CubismFormatError, match=r"broken\.exp3\.json: malformed JSON \("):
        load_exp3(path)
    with pytest.raises(FileNotFoundError):
        load_cdi3(tmp_path / "missing.cdi3.json")


def test_bom_prefixed_json_is_accepted(tmp_path):
    path = tmp_path / "bom.cdi3.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(
        {"Parts": [{"Id": "PartA", "Name": "Arm"}]}).encode("utf-8"))
    assert load_cdi3(path) == {"PartA": "Arm"}


def test_exp3_serialised_form_and_errors(tmp_path):
    path = tmp_path / "smile.exp3.json"
    _write(path, {"Type": "Live2D Expression", "Parameters": [
        {"Id": "A", "Value": 1},
        {"Id": 5, "Blend": "Multiply"},
        {"Id": "C", "Value": 0.5, "Blend": "Overwrite"},
    ]})
    assert asdict(load_exp3(path)) == {"name": "smile", "params": [
        {"id": "A", "value": 1.0, "mode": "additive"},
        {"id": "5", "value": 0.0, "mode": "multiply"},
        {"id": "C", "value": 0.5, "mode": "overwrite"},
    ]}
    wrong = tmp_path / "wrong.exp3.json"
    _write(wrong, {"Type": "Other"})
    with pytest.raises(CubismFormatError) as info:
        load_exp3(wrong)
    assert str(info.value) == f"{wrong} Type 'Other' is not 'Live2D Expression'"
    blend = tmp_path / "blend.exp3.json"
    _write(blend, {"Parameters": [{"Id": "A", "Blend": "Screen"}]})
    with pytest.raises(CubismFormatError) as info:
        load_exp3(blend)
    assert str(info.value) == (
        "unknown Cubism expression Blend 'Screen'; "
        "expected one of ['Add', 'Multiply', 'Overwrite']"
    )


def test_physics3_serialised_form(tmp_path):
    path = tmp_path / "rig.physics3.json"
    source = {"Source": {"Target": "Parameter", "Id": "ParamAngleX"}}
    dest = {"Destination": {"Target": "Parameter", "Id": "ParamHair"}}
    _write(path, {"PhysicsSettings": [
        {"Id": "Hair", "Input": [source], "Output": [dest], "Vertices": [
            {},
            {"Mobility": 0.5, "Delay": 0.5, "Acceleration": 2, "Radius": 3},
            {"Mobility": "x", "Delay": 9, "Acceleration": -1, "Radius": -1},
        ]},
        {"Id": 3, "Input": [source], "Output": [dest], "Vertices": [{}]},
        {"Id": "NoVerts", "Input": [source], "Output": [dest], "Vertices": []},
        {"Id": "NoInputs", "Input": [], "Output": [dest], "Vertices": [{}]},
        {"Id": "BadSrc", "Input": [{"Source": {"Target": "Part", "Id": "X"}}],
         "Output": [dest], "Vertices": [{}]},
        {"Id": "BadDst", "Input": [source], "Output": [{"Destination": "X"}],
         "Vertices": [{}]},
        {"Id": "NumId", "Input": [{"Source": {"Target": "Parameter", "Id": 1}}],
         "Output": [dest], "Vertices": [{}]},
    ]})
    rigs = load_physics3(path)
    assert len(rigs) == 1
    data = asdict(rigs[0])
    chain = data.pop("chain")
    assert data["id"] == "Hair"
    assert (data["input_param"], data["output_param"]) == ("ParamAngleX", "ParamHair")
    expected = [(1.0, 0.1, 2.4), (2.0, 0.55, 10.8), (0.5, 0.1, 1.2)]
    for particle, (mass, damping, spring) in zip(chain, expected, strict=True):
        assert particle["mass"] == pytest.approx(mass)
        assert particle["damping"] == pytest.approx(damping)
        assert particle["spring"] == pytest.approx(spring)


def test_physics3_without_settings(tmp_path):
    path = tmp_path / "empty.physics3.json"
    _write(path, {})
    assert load_physics3(path) == []


def test_pose3_serialised_form_and_type_error(tmp_path):
    path = tmp_path / "rig.pose3.json"
    _write(path, {"Type": "Live2D Pose", "Groups": [
        [{"Id": "ArmA", "Link": ["ArmA2", "", 4]}, "skip", {"Id": ""}, {"Id": "ArmB"}],
        "not-a-list",
        [{"Id": 3}],
        [{"Link": ["Only"]}],
    ]})
    assert [asdict(g) for g in load_pose3(path)] == [
        {"id": "pose_group_0", "drawables": ["ArmA", "ArmA2", "ArmB"]},
        {"id": "pose_group_3", "drawables": ["Only"]},
    ]
    wrong = tmp_path / "wrong.pose3.json"
    _write(wrong, {"Type": "Live2D Physics"})
    with pytest.raises(CubismFormatError) as info:
        load_pose3(wrong)
    assert str(info.value) == f"{wrong} Type 'Live2D Physics' is not 'Live2D Pose'"


def test_cdi3_mapping_skips_malformed_entries(tmp_path):
    path = tmp_path / "rig.cdi3.json"
    _write(path, {
        "Parameters": [{"Id": "P", "Name": "Param"}, {"Id": "Q", "Name": ""}, "x"],
        "ParameterGroups": [{"Id": "G", "Name": "Group"}, {"Id": 1, "Name": "N"}],
        "Parts": [{"Id": "P", "Name": "Part wins"}, {"Id": "R"}],
    })
    assert load_cdi3(path) == {"P": "Part wins", "G": "Group"}


def _write_full_model(tmp_path):
    _write(tmp_path / "motions" / "idle_01.motion3.json", _MOTION_RAW)
    _write(tmp_path / "exp" / "smile.exp3.json", {"Parameters": [{"Id": "A", "Value": 1}]})
    _write(tmp_path / "rig.physics3.json", {"PhysicsSettings": [{
        "Id": "Hair",
        "Input": [{"Source": {"Target": "Parameter", "Id": "In"}}],
        "Output": [{"Destination": {"Target": "Parameter", "Id": "Out"}}],
        "Vertices": [{}],
    }]})
    _write(tmp_path / "rig.pose3.json", {"Groups": [[{"Id": "ArmA"}, {"Id": "ArmB"}]]})
    _write(tmp_path / "rig.cdi3.json", {"Parameters": [{"Id": "In", "Name": "Input"}]})
    model = tmp_path / "rig.model3.json"
    _write(model, {
        "FileReferences": {
            "Motions": {
                "Idle": [
                    {"File": "motions/idle_01.motion3.json"},
                    {"File": "motions/idle_01.motion3.json", "FadeInTime": 1,
                     "FadeOutTime": 2.5, "Sound": "s/tap.wav"},
                    "not-a-dict",
                    {"File": ""},
                    {"FadeInTime": 1},
                    {"File": "motions/idle_01.motion3.json", "FadeInTime": "x",
                     "Sound": ""},
                ],
                "Broken": "not-a-list",
            },
            "Expressions": [
                {"Name": "Joy", "File": "exp/smile.exp3.json"},
                {"File": "exp/smile.exp3.json"},
                {"Name": "NoFile"},
                3,
            ],
            "Physics": "rig.physics3.json",
            "Pose": "rig.pose3.json",
            "DisplayInfo": "rig.cdi3.json",
        },
        "Groups": [
            {"Target": "Parameter", "Name": "EyeBlink", "Ids": ["L", 2]},
            {"Target": "Part", "Name": "Ignored", "Ids": ["X"]},
            {"Target": "Parameter", "Name": "NoIds"},
            "x",
        ],
        "HitAreas": [
            {"Id": "HitHead", "Name": "Head"},
            {"Id": "HitBody"},
            {"Name": "NoId"},
            "x",
        ],
    })
    return model


def test_model3_bundle_serialised_form(tmp_path):
    bundle = load_model3(_write_full_model(tmp_path))
    data = asdict(bundle)
    assert data["motions"] == [
        _motion_dict("Idle/idle_01", group="Idle"),
        _motion_dict("Idle/idle_01", fade_in=1.0, fade_out=2.5, group="Idle",
                     sound=str(tmp_path / "s/tap.wav")),
        _motion_dict("Idle/idle_01", group="Idle"),
    ]
    assert data["expressions"] == [
        {"name": "Joy", "params": [{"id": "A", "value": 1.0, "mode": "additive"}]},
        {"name": "smile", "params": [{"id": "A", "value": 1.0, "mode": "additive"}]},
    ]
    assert data["hit_areas"] == [
        asdict(HitArea(id="Head", drawables=["HitHead"])),
        asdict(HitArea(id="HitBody", drawables=["HitBody"])),
    ]
    assert [(r["id"], r["input_param"], r["output_param"]) for r in data["physics_rigs"]] == [
        ("Hair", "In", "Out"),
    ]
    assert data["pose_groups"] == [{"id": "pose_group_0", "drawables": ["ArmA", "ArmB"]}]
    assert data["display_names"] == {"In": "Input"}
    assert data["parameter_groups"] == {"EyeBlink": ["L", "2"]}


def test_model3_without_references_is_empty(tmp_path):
    model = tmp_path / "bare.model3.json"
    _write(model, {"FileReferences": {"Physics": "", "Pose": 3, "DisplayInfo": None}})
    assert asdict(load_model3(model)) == asdict(CubismBundle())


def test_model3_propagates_referenced_file_errors(tmp_path):
    model = tmp_path / "rig.model3.json"
    _write(model, {"FileReferences": {"Expressions": [{"File": "gone.exp3.json"}]}})
    with pytest.raises(FileNotFoundError):
        load_model3(model)


def test_apply_bundle_dedupes_and_merges_display_names():
    doc = PuppetDocument()
    doc.motions.append(Motion(name="Idle/a", duration=0.0))
    doc.display_names["Old"] = "Kept"
    bundle = CubismBundle(
        motions=[Motion(name="Idle/a", duration=9.0), Motion(name="Idle/b", duration=0.0),
                 Motion(name="Idle/b", duration=3.0)],
        hit_areas=[HitArea(id="Head", drawables=[]), HitArea(id="Head", drawables=["x"])],
        display_names={"New": "Added"},
    )
    apply_bundle(doc, bundle)
    assert [(m.name, m.duration) for m in doc.motions] == [("Idle/a", 0.0), ("Idle/b", 0.0)]
    assert [(h.id, h.drawables) for h in doc.hit_areas] == [("Head", [])]
    assert doc.display_names == {"Old": "Kept", "New": "Added"}


def test_format_error_is_value_error_and_reexported():
    assert issubclass(CubismFormatError, ValueError)
    for name in ("_read_json", "_load_motion_entry", "_consume_segment",
                 "_CUBISM_BEZIER", "_CUBISM_LINEAR"):
        assert hasattr(cubism_import, name)
