"""Golden values for the physics chains.

Recorded from the numpy integrator before it was rewritten on plain floats,
so any change to the arithmetic shows up here. Qt-free: runs on CI.
"""
from __future__ import annotations

import pytest

from Imervue.puppet.document import PhysicsParticle, PhysicsRig, PuppetDocument
from Imervue.puppet.physics import PhysicsEngine

_TIGHT = {"rel": 1e-12, "abs": 1e-15}


def _rigs() -> list[PhysicsRig]:
    return [
        PhysicsRig("hair", "In", "OutHair", [PhysicsParticle(1.0, 0.7, 12.0),
                                              PhysicsParticle(0.8, 0.7, 12.0),
                                              PhysicsParticle(0.6, 0.7, 12.0)], (0.0, -9.8)),
        # Out-of-range damping and a negative spring are clamped; a sideways gravity.
        PhysicsRig("ribbon", "In", "OutRibbon", [PhysicsParticle(1.0, 0.2, 30.0),
                                                  PhysicsParticle(1.0, 0.95, 3.0),
                                                  PhysicsParticle(1.0, 1.5, -2.0),
                                                  PhysicsParticle(1.0, 0.0, 80.0)], (2.5, 4.0)),
        # No particles: the output follows the input.
        PhysicsRig("stub", "Other", "OutStub", [], (0.0, -9.8)),
    ]


_STEPS = [(1 / 60, 0.8, -0.3), (1 / 30, -1.0, 0.4), (0.005, 0.25, 0.0), (0.02, 0.0, 1.0),
          (0.1, -0.6, -0.2)]

_OUTPUTS = {
    0: (0.03200000000000001, 2.314814814814815e-05, -0.3),
    3: (-0.18582307648000002, 0.00015127534724537037, 1.0),
    7: (-0.6380920377718668, 0.0011589304294398087, 0.0),
    12: (-0.5506641728202064, 0.0021444066463975073, 0.0),
    20: (-0.566913713437044, 0.003965052181778072, -0.3),
    29: (-0.6, 0.005912023100876476, -0.2),
}
_HAIR_END = [(-18.0, 0.0), (-18.0, -30.0), (-18.0, -60.0)]
_RIBBON_END = [(-18.0, 0.0), (-14.332718908735544, -29.929331640390537),
               (0.17736069302629429, -59.716222891157884),
               (0.17736069302629429, -89.71622289115788)]


@pytest.fixture
def run():
    doc = PuppetDocument(size=(100, 100))
    doc.physics_rigs = _rigs()
    engine = PhysicsEngine()
    engine.bind_document(doc)
    trace = []
    for _repeat in range(6):
        for dt, first, second in _STEPS:
            out = engine.step(dt, {"In": first, "Other": second})
            trace.append((out["OutHair"], out["OutRibbon"], out["OutStub"]))
    return engine, trace


def test_the_outputs_match_the_recorded_values(run):
    _engine, trace = run
    for index, expected in _OUTPUTS.items():
        assert trace[index] == pytest.approx(expected, **_TIGHT), index


@pytest.mark.parametrize(("rig_id", "expected"), [("hair", _HAIR_END), ("ribbon", _RIBBON_END)])
def test_the_particles_end_where_they_did(run, rig_id, expected):
    engine, _trace = run
    positions = engine.particle_positions(rig_id)
    assert positions.shape == (len(expected), 2)
    assert positions.tolist() == [pytest.approx(list(p), **_TIGHT) for p in expected]


def test_reset_returns_every_chain_to_rest(run):
    engine, _trace = run
    engine.reset()
    assert engine.particle_positions("ribbon").tolist() == [
        [0.0, 0.0], [0.0, -30.0], [0.0, -60.0], [0.0, -90.0]]
