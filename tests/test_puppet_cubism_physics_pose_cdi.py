"""Tests for the Cubism ``.physics3.json``, ``.pose3.json``, and
``.cdi3.json`` importers, plus the model3 bundle integration that
pulls them via ``FileReferences``.
"""
from __future__ import annotations

import json

from Imervue.puppet.cubism_import import (
    load_cdi3,
    load_model3,
    load_physics3,
    load_pose3,
)


# ---------------------------------------------------------------------------
# .physics3.json
# ---------------------------------------------------------------------------


def test_load_physics3_maps_settings_to_physics_rigs(tmp_path):
    p = tmp_path / "model.physics3.json"
    p.write_text(json.dumps({
        "Version": 3,
        "PhysicsSettings": [
            {
                "Id": "PhysicsSetting1",
                "Input": [
                    {"Source": {"Target": "Parameter", "Id": "ParamAngleX"},
                     "Weight": 100.0, "Type": "Angle"},
                ],
                "Output": [
                    {"Destination": {"Target": "Parameter", "Id": "ParamHairFront"},
                     "VertexIndex": 1, "Scale": 1.0, "Weight": 100.0, "Type": "Angle"},
                ],
                "Vertices": [
                    {"Position": {"X": 0, "Y": 0}},
                    {"Position": {"X": 0, "Y": 1}},
                    {"Position": {"X": 0, "Y": 2}},
                ],
            },
        ],
    }), encoding="utf-8")
    rigs = load_physics3(p)
    assert len(rigs) == 1
    rig = rigs[0]
    assert rig.id == "PhysicsSetting1"
    assert rig.input_param == "ParamAngleX"
    assert rig.output_param == "ParamHairFront"
    assert len(rig.chain) == 3


def test_load_physics3_skips_setting_with_missing_endpoints(tmp_path):
    p = tmp_path / "broken.physics3.json"
    p.write_text(json.dumps({
        "Version": 3,
        "PhysicsSettings": [
            {"Id": "x", "Input": [], "Output": [], "Vertices": []},
        ],
    }), encoding="utf-8")
    assert load_physics3(p) == []


# ---------------------------------------------------------------------------
# .pose3.json
# ---------------------------------------------------------------------------


def test_load_pose3_builds_one_group_per_mutex_set(tmp_path):
    p = tmp_path / "model.pose3.json"
    p.write_text(json.dumps({
        "Type": "Live2D Pose",
        "Groups": [
            [
                {"Id": "PartArmLA", "Link": ["PartArmLB"]},
                {"Id": "PartArmRA", "Link": []},
            ],
            [
                {"Id": "PartWeapon1", "Link": []},
                {"Id": "PartWeapon2", "Link": []},
            ],
        ],
    }), encoding="utf-8")
    groups = load_pose3(p)
    assert len(groups) == 2
    # Primary + link ids both end up in drawables list
    assert "PartArmLA" in groups[0].drawables
    assert "PartArmLB" in groups[0].drawables
    assert "PartArmRA" in groups[0].drawables
    assert set(groups[1].drawables) == {"PartWeapon1", "PartWeapon2"}


# ---------------------------------------------------------------------------
# .cdi3.json
# ---------------------------------------------------------------------------


def test_load_cdi3_collects_parameter_and_part_names(tmp_path):
    p = tmp_path / "model.cdi3.json"
    p.write_text(json.dumps({
        "Version": 3,
        "Parameters": [
            {"Id": "ParamAngleX", "Name": "Head X"},
            {"Id": "ParamMouthOpenY", "Name": "Mouth Open"},
        ],
        "ParameterGroups": [
            {"Id": "FaceGroup", "Name": "Face"},
        ],
        "Parts": [
            {"Id": "PartHair", "Name": "Hair"},
        ],
    }), encoding="utf-8")
    names = load_cdi3(p)
    assert names == {
        "ParamAngleX": "Head X",
        "ParamMouthOpenY": "Mouth Open",
        "FaceGroup": "Face",
        "PartHair": "Hair",
    }


# ---------------------------------------------------------------------------
# Model3 bundle picks them up
# ---------------------------------------------------------------------------


def _write_motion3(path):
    path.write_text(json.dumps({
        "Version": 3,
        "Meta": {"Duration": 1.0, "Fps": 30, "Loop": False},
        "Curves": [
            {"Target": "Parameter", "Id": "ParamAngleX",
             "Segments": [0.0, 0.0,   0, 1.0, 1.0]},
        ],
    }), encoding="utf-8")


def test_model3_bundles_physics_pose_and_cdi(tmp_path):
    motion_path = tmp_path / "motion.motion3.json"
    _write_motion3(motion_path)
    physics_path = tmp_path / "phys.physics3.json"
    physics_path.write_text(json.dumps({
        "Version": 3,
        "PhysicsSettings": [
            {
                "Id": "rig1",
                "Input": [{"Source": {"Target": "Parameter", "Id": "ParamAngleX"}}],
                "Output": [{"Destination": {"Target": "Parameter", "Id": "ParamHairFront"}}],
                "Vertices": [{"Position": {"X": 0, "Y": 0}}],
            },
        ],
    }), encoding="utf-8")
    pose_path = tmp_path / "pose.pose3.json"
    pose_path.write_text(json.dumps({
        "Type": "Live2D Pose",
        "Groups": [[{"Id": "X", "Link": []}]],
    }), encoding="utf-8")
    cdi_path = tmp_path / "names.cdi3.json"
    cdi_path.write_text(json.dumps({
        "Parameters": [{"Id": "ParamAngleX", "Name": "Head"}],
    }), encoding="utf-8")
    model_path = tmp_path / "model.model3.json"
    model_path.write_text(json.dumps({
        "Version": 3,
        "FileReferences": {
            "Motions": {"Idle": [{"File": motion_path.name}]},
            "Physics": physics_path.name,
            "Pose": pose_path.name,
            "DisplayInfo": cdi_path.name,
        },
    }), encoding="utf-8")
    bundle = load_model3(model_path)
    assert [r.id for r in bundle.physics_rigs] == ["rig1"]
    assert len(bundle.pose_groups) == 1
    assert bundle.display_names == {"ParamAngleX": "Head"}
