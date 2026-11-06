"""The illustrated mascot retains original pixels and meaningful live controls."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.puppet.document_io import load_puppet
from Imervue.puppet.format_schema import check_puppet_file
from Imervue.puppet.hit_test import hit_test
from Imervue.puppet.runtime import (
    compose_all_drawables,
    default_parameter_values,
    resolve_drawable_opacity,
)
from Imervue.puppet.standard_params import standard_parameter_ids

ROOT = Path(__file__).resolve().parents[1]
RIG = ROOT / "examples/puppet/imeru.puppet"
ART = ROOT / "examples/puppet/imeru/artwork"


@pytest.fixture(scope="module")
def doc():
    return load_puppet(RIG)


def test_bundled_archive_is_valid_and_the_only_example():
    report = check_puppet_file(RIG)
    assert report["valid"] and report["issues"] == []
    assert sorted(p.name for p in RIG.parent.glob("*.puppet")) == ["imeru.puppet"]


def test_original_illustration_pixels_are_preserved(doc):
    assert doc.size == (1024, 1664)
    for name in ("master", "underlay", "alternates", "arms"):
        assert doc.textures[f"textures/{name}.png"] == (ART / f"{name}.png").read_bytes()
    body = doc.drawable("body")
    np.testing.assert_allclose(np.asarray(body.uvs) * (1024, 1536) + (0, 64), body.vertices, atol=1e-5)


def test_hair_boots_and_transparent_background(doc):
    with Image.open(io.BytesIO(doc.textures["textures/underlay.png"])) as image:
        pixels = np.asarray(image)
    assert (pixels[:10, :, 3] == 0).mean() > 0.98
    assert (pixels[30:100, 460:530, 3] > 230).mean() > 0.9
    assert (pixels[270:370, 340:400, 3] > 230).mean() > 0.7
    for x in (440, 695):
        assert (pixels[1400:1470, x - 15 : x + 15, 3] > 230).mean() > 0.7
    assert max(y for _, y in doc.drawable("body").vertices) > 1480


def test_every_parameter_has_a_visual_binding(doc):
    ids = {p.id for p in doc.parameters}
    assert ids == set(standard_parameter_ids()) | {
        "ParamArmRA",
        "ParamArmRB",
        "ParamArmLA",
        "ParamArmLB",
    }
    bound = {p.id for p in doc.parameters if p.keys}
    for d in doc.drawables:
        for attr in ("vertex_morphs", "opacity_keys", "multiply_color_keys"):
            bound.update(item["parameter"] for item in getattr(d, attr) or [])
    assert ids == bound


@pytest.mark.parametrize("side", ["r", "l"])
def test_sleeve_is_connected_and_elbow_weights_blend(doc, side):
    d = doc.drawable(f"arm_{side}")
    adjacency = {i: set() for i in range(len(d.vertices))}
    for tri in np.asarray(d.indices).reshape(-1, 3):
        for vertex in tri:
            adjacency[vertex].update(tri)
    shoulder = next(node for node in doc.deformers if node.id == f"shoulder_{side}")
    vertices = np.asarray(d.vertices)
    start = np.linalg.norm(vertices - shoulder.form["anchor"], axis=1).argmin()
    cuff = (255, 717) if side == "r" else (774, 721)
    end = np.linalg.norm(vertices - cuff, axis=1).argmin()
    visited, pending = set(), [start]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(adjacency[current] - visited)
    assert end in visited
    assert len(visited) > .98 * len(d.vertices)
    fixed = np.asarray(d.bone_weights[f"fixed_{side}"])
    bend = np.asarray(d.bone_weights[f"bend_{side}"])
    np.testing.assert_allclose(fixed + bend, 1.0)
    assert ((bend > 0.1) & (bend < 0.9)).sum() > 20


@pytest.mark.parametrize("side", ["r", "l"])
def test_wave_lifts_hand_without_stretching(doc, side):
    values = default_parameter_values(doc)
    rest = compose_all_drawables(doc, values)
    wave = compose_all_drawables(
        doc, {**values, f"ParamArm{side.upper()}A": 1.0, f"ParamArm{side.upper()}B": 0.86}
    )
    shoulder = next(d for d in doc.deformers if d.id == f"shoulder_{side}")
    a, b = np.asarray(rest[f"hand_open_{side}"]), np.asarray(wave[f"hand_open_{side}"])
    assert b[:, 1].mean() < shoulder.form["anchor"][1] < a[:, 1].mean()
    np.testing.assert_allclose(
        np.linalg.norm(a - a.mean(axis=0), axis=1),
        np.linalg.norm(b - b.mean(axis=0), axis=1),
        atol=0.001,
    )


@pytest.mark.parametrize("side", ["r", "l"])
def test_blink_and_smile_replace_open_eyes(doc, side):
    values = default_parameter_values(doc)
    closed = {**values, f"ParamEye{side.upper()}Open": 0.0}
    smiling = {**values, f"ParamEye{side.upper()}Smile": 1.0}
    assert resolve_drawable_opacity(doc.drawable(f"eye_{side}"), closed) == 0.0
    assert resolve_drawable_opacity(doc.drawable(f"closed_{side}"), closed) == 1.0
    assert resolve_drawable_opacity(doc.drawable(f"eye_{side}"), smiling) == 0.0
    assert resolve_drawable_opacity(doc.drawable(f"smile_{side}"), smiling) == 1.0


@pytest.mark.parametrize("side", ["r", "l"])
def test_gaze_moves_interior_but_pins_eye_corners(doc, side):
    values = default_parameter_values(doc)
    rest = np.asarray(compose_all_drawables(doc, values)[f"eye_{side}"])
    looked = np.asarray(compose_all_drawables(doc, {**values, "ParamEyeBallX": 1.0})[f"eye_{side}"])
    boundary = (
        (rest[:, 0] == rest[:, 0].min())
        | (rest[:, 0] == rest[:, 0].max())
        | (rest[:, 1] == rest[:, 1].min())
        | (rest[:, 1] == rest[:, 1].max())
    )
    np.testing.assert_allclose(rest[boundary], looked[boundary], atol=0.001)
    assert (looked[:, 0] - rest[:, 0]).max() > 2.0


def test_mouth_and_cheek_controls_show_visible_art(doc):
    values = default_parameter_values(doc)
    assert resolve_drawable_opacity(doc.drawable("mouth_open"), values) == 0.0
    opened = {**values, "ParamMouthOpenY": 0.8}
    assert resolve_drawable_opacity(doc.drawable("mouth_open"), opened) == 1.0
    assert resolve_drawable_opacity(doc.drawable("mouth_rest"), opened) == 0.0
    assert resolve_drawable_opacity(doc.drawable("cheek_r_0"), values) == 0.0
    assert resolve_drawable_opacity(doc.drawable("cheek_r_0"), {**values, "ParamCheek": 1.0}) > 0.2


def test_breathing_keeps_legs_and_feet_planted(doc):
    values = default_parameter_values(doc)
    rest = np.asarray(compose_all_drawables(doc, values)["body"])
    breath = np.asarray(compose_all_drawables(doc, {**values, "ParamBreath": 1.0})["body"])
    np.testing.assert_allclose(rest[rest[:, 1] > 790], breath[rest[:, 1] > 790], atol=0.001)
    assert np.abs(rest - breath).max() > 1.0


@pytest.mark.parametrize("parameter", ["ParamAngleX", "ParamAngleY", "ParamAngleZ"])
def test_head_turns_preserve_mesh_orientation(doc, parameter):
    values = default_parameter_values(doc)
    indices = np.asarray(doc.drawable("body").indices).reshape(-1, 3)

    def signed(v):
        tri = np.asarray(v)[indices]
        a, b = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        return a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]

    base = signed(compose_all_drawables(doc, values)["body"])
    for value in (-1.0, 1.0):
        changed = signed(compose_all_drawables(doc, {**values, parameter: value})["body"])
        assert (base * changed > 0.0).all()


def test_crown_and_jacket_have_distinct_hit_responses(doc):
    assert hit_test(doc, 510, 110) == "Head"
    assert hit_test(doc, 510, 400) == "Body"
    assert hit_test(doc, 30, 1400) is None


def test_motions_expressions_and_pet_script_remain_compatible(doc):
    assert {m.name: m.group for m in doc.motions} == {
        "idle_breath": "Idle",
        "idle_look": "Idle",
        "tap_head": "TapHead",
        "greet": "Gesture",
        "wave": "Gesture",
        "surprised": "Gesture",
        "shy": "TapBody",
        "sleepy": "Gesture",
    }
    assert {e.name for e in doc.expressions} == {
        "smile",
        "happy",
        "surprised",
        "sad",
        "angry",
        "blush",
        "sleepy",
    }
    assert {a.id: a.motion for a in doc.hit_areas} == {"Head": "TapHead", "Body": "TapBody"}
    ids = {p.id for p in doc.parameters}
    for motion in doc.motions:
        assert {t.param_id for t in motion.tracks} <= ids
    for chain in doc.physics_rigs:
        assert {chain.input_param, chain.output_param} <= ids
    script = json.loads((ROOT / "examples/desktop_pet/imeru.petscript.json").read_text(encoding="utf-8"))
    assert set(script["hit_responses"]) == {a.id for a in doc.hit_areas}
    assert set(script["motion_lines"]) <= {m.name for m in doc.motions}


def test_builder_uses_illustrations_without_starting_blender(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("imeru_build", ART.parent / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def reject_render(*args, **kwargs):
        pytest.fail("The illustrated builder must not launch Blender")

    monkeypatch.setattr(module.render3d, "render", reject_render)
    output = tmp_path / "illustrated.puppet"
    report = module.build(output)
    assert report["valid"] and not report["issues"]
    assert load_puppet(output).textures == load_puppet(RIG).textures


def test_ribbon_stays_with_shoulder_when_elbow_bends(doc):
    arm = doc.drawable("arm_l")
    source = np.asarray(arm.uvs) * (1024, 1536)
    tail = (source[:, 0] > 970) & (source[:, 1] > 645) & (source[:, 1] < 675)
    assert tail.sum() > 5
    values = default_parameter_values(doc)
    rest = np.asarray(compose_all_drawables(doc, values)["arm_l"])
    bent = np.asarray(compose_all_drawables(doc, {**values, "ParamArmLB": 1.0})["arm_l"])
    np.testing.assert_allclose(rest[tail], bent[tail], atol=.001)


@pytest.mark.parametrize("sign", [-1, 1])
def test_combined_turn_and_wave_stays_inside_canvas(doc, sign):
    values = default_parameter_values(doc)
    values.update({name: sign for name in (
        "ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBodyAngleX",
        "ParamBodyAngleY", "ParamBodyAngleZ", "ParamHairFront", "ParamHairSide", "ParamHairBack",
    )})
    values.update(ParamArmLA=1., ParamArmLB=.86, ParamArmRA=1., ParamArmRB=.86)
    posed = compose_all_drawables(doc, values)
    for drawable in doc.drawables:
        if resolve_drawable_opacity(drawable, values) > 0:
            vertices = np.asarray(posed[drawable.id])
            assert (vertices.min(axis=0) >= (0, 0)).all(), drawable.id
            assert (vertices.max(axis=0) <= doc.size).all(), drawable.id
