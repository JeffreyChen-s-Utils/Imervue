"""Pure-numpy tests for the verlet physics engine + canvas
integration smoke."""
from __future__ import annotations
import pytest

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import (
    Drawable,
    Parameter,
    PhysicsParticle,
    PhysicsRig,
    PuppetDocument,
)
from Imervue.puppet.physics import PhysicsEngine, REST_LENGTH

from _qt_skip import pytestmark  # noqa: E402,F401


def _hair_rig() -> PhysicsRig:
    return PhysicsRig(
        id="front_hair",
        input_param="ParamBodyAngleX",
        output_param="ParamHairFront",
        chain=[
            PhysicsParticle(mass=1.0, damping=0.7, spring=12.0),
            PhysicsParticle(mass=0.8, damping=0.7, spring=12.0),
            PhysicsParticle(mass=0.6, damping=0.7, spring=12.0),
        ],
        gravity=(0.0, -9.8),
    )


def _doc_with_physics() -> PuppetDocument:
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [
        Drawable(
            id="hair", texture="textures/x.png",
            vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
            draw_order=0,
        ),
    ]
    doc.parameters = [
        Parameter(id="ParamBodyAngleX", min=-1.0, max=1.0, default=0.0, keys=[]),
        Parameter(id="ParamHairFront", min=-1.0, max=1.0, default=0.0, keys=[]),
    ]
    doc.physics_rigs = [_hair_rig()]
    return doc


# ---------------------------------------------------------------------------
# Engine basics
# ---------------------------------------------------------------------------


def test_bind_document_creates_one_state_per_rig():
    engine = PhysicsEngine()
    doc = _doc_with_physics()
    engine.bind_document(doc)
    assert engine.chain_ids() == ["front_hair"]


def test_bind_document_none_clears():
    engine = PhysicsEngine()
    engine.bind_document(_doc_with_physics())
    engine.bind_document(None)
    assert engine.chain_ids() == []


def test_initial_positions_match_rest_pose():
    engine = PhysicsEngine()
    engine.bind_document(_doc_with_physics())
    pos = engine.particle_positions("front_hair")
    # Particle 0 at (0, 0); each subsequent at +REST_LENGTH down (–y)
    assert pos.shape == (3, 2)
    assert pos[0].tolist() == [0.0, 0.0]
    assert pos[1].tolist() == [0.0, -REST_LENGTH]
    assert pos[2].tolist() == [0.0, -2 * REST_LENGTH]


def test_step_with_zero_dt_is_noop():
    engine = PhysicsEngine()
    engine.bind_document(_doc_with_physics())
    out = engine.step(0.0, {"ParamBodyAngleX": 1.0})
    assert out == {}


def test_step_with_no_input_keeps_chain_at_rest():
    engine = PhysicsEngine()
    engine.bind_document(_doc_with_physics())
    for _ in range(120):   # 2s at 60fps
        engine.step(1.0 / 60.0, {})
    pos = engine.particle_positions("front_hair")
    # Tip stays close to rest (negligible lateral drift)
    assert abs(pos[-1, 0]) < 0.5


def test_input_parameter_drives_anchor_laterally():
    engine = PhysicsEngine()
    engine.bind_document(_doc_with_physics())
    engine.step(1.0 / 60.0, {"ParamBodyAngleX": 1.0})
    pos = engine.particle_positions("front_hair")
    # Anchor at REST_LENGTH * 1.0 → REST_LENGTH px to the right
    assert pos[0, 0] == pytest.approx(REST_LENGTH)


def test_chain_settles_after_input_swing():
    """Push the anchor right, then hold steady — the tip should
    eventually catch up and the absolute lateral velocity decays."""
    engine = PhysicsEngine()
    engine.bind_document(_doc_with_physics())
    # Drive anchor to the right at an extreme
    engine.step(1.0 / 60.0, {"ParamBodyAngleX": 1.0})
    last_tip = engine.particle_positions("front_hair")[-1, 0]
    distances = [last_tip]
    for _ in range(180):   # 3s of steady input
        engine.step(1.0 / 60.0, {"ParamBodyAngleX": 1.0})
        distances.append(engine.particle_positions("front_hair")[-1, 0])
    # By the end the chain should be measurably closer to the anchor
    # column than it started
    assert distances[-1] > distances[0]


def test_step_returns_output_for_every_rig():
    engine = PhysicsEngine()
    engine.bind_document(_doc_with_physics())
    out = engine.step(1.0 / 60.0, {"ParamBodyAngleX": 0.5})
    assert "ParamHairFront" in out
    assert -1.0 <= out["ParamHairFront"] <= 1.0


def test_reset_returns_chain_to_rest_pose():
    engine = PhysicsEngine()
    engine.bind_document(_doc_with_physics())
    for _ in range(30):
        engine.step(1.0 / 60.0, {"ParamBodyAngleX": 1.0})
    engine.reset()
    pos = engine.particle_positions("front_hair")
    assert pos[-1, 0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Canvas integration
# ---------------------------------------------------------------------------


def test_canvas_load_document_binds_physics(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_physics())
    try:
        assert canvas.physics().chain_ids() == ["front_hair"]
    finally:
        canvas.deleteLater()


def test_canvas_step_physics_writes_output_param(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_physics())
    try:
        canvas.set_parameter_value("ParamBodyAngleX", 1.0)
        canvas.step_physics(1.0 / 60.0)
        # Physics layered output
        assert "ParamHairFront" in canvas._physics_outputs   # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_canvas_step_physics_with_no_document_is_safe(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.step_physics(1.0 / 60.0)   # must not raise
    finally:
        canvas.deleteLater()
