"""The bundled example character, Imeru: a valid file, a working rig, and a pet script that fits it."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from Imervue.puppet.document import PuppetDocument
from Imervue.puppet.document_io import load_puppet
from Imervue.puppet.format_schema import check_puppet_file
from Imervue.puppet.runtime import compose_all_drawables, default_parameter_values
from Imervue.puppet.standard_params import standard_parameter_ids

_ROOT = Path(__file__).resolve().parents[1]
_RIG = _ROOT / "examples" / "puppet" / "imeru.puppet"
_SCRIPT = _ROOT / "examples" / "desktop_pet" / "imeru.petscript.json"


@pytest.fixture(scope="module")
def doc() -> PuppetDocument:
    return load_puppet(_RIG)


def test_the_bundled_file_passes_the_format_check_without_a_note():
    report = check_puppet_file(_RIG)
    assert report["valid"] is True
    assert report["issues"] == []


def test_it_is_the_only_bundled_rig():
    assert sorted(p.name for p in (_ROOT / "examples" / "puppet").glob("*.puppet")) == ["imeru.puppet"]


def test_every_standard_parameter_and_the_arm_parameters_are_there(doc):
    ids = {p.id for p in doc.parameters}
    assert set(standard_parameter_ids()) <= ids
    assert {"ParamArmRA", "ParamArmRB", "ParamArmLA", "ParamArmLB"} <= ids


def test_the_forearms_bend_before_the_arms_turn(doc):
    """No deformer passes its transform to another, so array order gives the arm its joints."""
    order = [d.id for d in doc.deformers]
    assert order == ["forearm_r", "forearm_l", "upper_arm_r", "upper_arm_l", "body_roll"]
    for side in ("r", "l"):
        forearm = next(d for d in doc.deformers if d.id == f"forearm_{side}")
        upper = next(d for d in doc.deformers if d.id == f"upper_arm_{side}")
        assert set(forearm.drawables) <= set(upper.drawables)


def _centre(vertices: dict, drawable: str) -> np.ndarray:
    return np.asarray(vertices[drawable]).mean(axis=0)


def test_raising_the_arm_lifts_the_hand_above_the_shoulder(doc):
    rest = compose_all_drawables(doc, default_parameter_values(doc))
    raised = compose_all_drawables(doc, {**default_parameter_values(doc),
                                         "ParamArmRA": 1.0, "ParamArmRB": 0.86})
    shoulder_y = _centre(rest, "upper_arm_r")[1] - 120
    assert _centre(raised, "hand_open_r")[1] < shoulder_y < _centre(rest, "hand_r")[1]
    forearm_rest = np.ptp(np.asarray(rest["forearm_r"]), axis=0).max()
    forearm_up = np.ptp(np.asarray(raised["forearm_r"]), axis=0).max()
    assert forearm_up == pytest.approx(forearm_rest, rel=0.05)    # turned, not stretched


def test_the_irises_are_clipped_to_the_whites(doc):
    for side in ("l", "r"):
        assert doc.drawable(f"iris_{side}").clip_mask == f"eye_white_{side}"
        assert doc.drawable(f"highlight_{side}").clip_mask == f"eye_white_{side}"


def _mesh_area(vertices, indices) -> float:
    tri = np.asarray(vertices)[np.asarray(indices).reshape(-1, 3)]
    cross = ((tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1])
             - (tri[:, 2, 0] - tri[:, 0, 0]) * (tri[:, 1, 1] - tri[:, 0, 1]))
    return float(np.abs(cross).sum() / 2)


@pytest.mark.parametrize(("side", "param"), [("l", "ParamEyeLOpen"), ("r", "ParamEyeROpen")])
def test_closing_an_eye_collapses_its_white(doc, side, param):
    """The iris is clipped to the white, so the white must close to nothing."""
    values = default_parameter_values(doc)
    indices = doc.drawable(f"eye_white_{side}").indices
    open_area = _mesh_area(compose_all_drawables(doc, values)[f"eye_white_{side}"], indices)
    shut = compose_all_drawables(doc, {**values, param: 0.0})[f"eye_white_{side}"]
    assert _mesh_area(shut, indices) < 0.02 * open_area


def test_motions_expressions_and_hit_areas(doc):
    motions = {m.name: m.group for m in doc.motions}
    assert motions == {"idle_breath": "Idle", "idle_look": "Idle", "tap_head": "TapHead",
                       "greet": "Gesture", "wave": "Gesture", "surprised": "Gesture",
                       "shy": "TapBody", "sleepy": "Gesture"}
    assert {e.name for e in doc.expressions} == {"smile", "happy", "surprised", "sad", "angry",
                                                  "blush", "sleepy"}
    groups = set(motions.values())
    assert {a.id: a.motion for a in doc.hit_areas} == {"Head": "TapHead", "Body": "TapBody"}
    assert {a.motion for a in doc.hit_areas} <= groups


def test_every_motion_track_drives_a_parameter_that_exists(doc):
    ids = {p.id for p in doc.parameters}
    for motion in doc.motions:
        assert {t.param_id for t in motion.tracks} <= ids, motion.name


def test_the_hair_physics_reads_and_writes_parameters_that_exist(doc):
    ids = {p.id for p in doc.parameters}
    for rig in doc.physics_rigs:
        assert {rig.input_param, rig.output_param} <= ids, rig.id


def test_the_pet_script_answers_her_hit_areas_and_motions(doc):
    script = json.loads(_SCRIPT.read_text(encoding="utf-8"))
    assert set(script["hit_responses"]) == {a.id for a in doc.hit_areas}
    assert set(script["motion_lines"]) <= {m.name for m in doc.motions}


def _build_module():
    spec = importlib.util.spec_from_file_location(
        "imeru_build", _ROOT / "examples" / "puppet" / "imeru" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_generator_trims_the_empty_top_of_the_canvas():
    from Imervue.puppet.document import Deformer, Drawable
    build = _build_module()
    doc = PuppetDocument(size=(100, 500))
    doc.drawables = [Drawable(id="a", texture="t.png", vertices=[(0.0, 250.0), (10.0, 300.0)],
                              indices=[], uvs=[(0, 0), (1, 1)])]
    doc.deformers = [Deformer(id="r", type="rotation", parent=None, drawables=["a"],
                              form={"anchor": [5.0, 400.0], "angle": 0.0})]
    build.trim_top(doc, 200)
    assert doc.size == (100, 300)
    assert doc.drawables[0].vertices == [(0.0, 50.0), (10.0, 100.0)]
    assert doc.deformers[0].form["anchor"] == [5.0, 200.0]
