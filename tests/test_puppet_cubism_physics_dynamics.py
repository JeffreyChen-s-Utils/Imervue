"""Tests for the Cubism physics-vertex → PhysicsParticle mapping.

The mapping is heuristic (mass-spring vs Cubism's proprietary
integrator), but two important invariants hold and we check them:

* Higher ``Mobility`` produces lower ``damping`` — a more mobile
  vertex stays in motion longer.
* Higher ``Delay`` produces lower ``spring`` — a delayed vertex
  takes longer to converge to its rest position.

Plus straightforward sanity bounds: damping in ``[0, 0.999]``,
spring positive, mass positive.
"""
from __future__ import annotations

import json

from puppet.cubism_import import load_physics3


def _write_physics3(path, vertex_props: list[dict]) -> None:
    path.write_text(json.dumps({
        "Version": 3,
        "PhysicsSettings": [
            {
                "Id": "rig",
                "Input": [
                    {"Source": {"Target": "Parameter", "Id": "ParamAngleX"}},
                ],
                "Output": [
                    {"Destination": {"Target": "Parameter", "Id": "ParamHairFront"}},
                ],
                "Vertices": vertex_props,
            },
        ],
    }), encoding="utf-8")


def test_higher_mobility_lowers_damping(tmp_path):
    p = tmp_path / "phys.physics3.json"
    _write_physics3(p, [
        {"Mobility": 0.1, "Delay": 0.5, "Acceleration": 1.0, "Radius": 1.0},
        {"Mobility": 0.9, "Delay": 0.5, "Acceleration": 1.0, "Radius": 1.0},
    ])
    rig = load_physics3(p)[0]
    assert rig.chain[0].damping > rig.chain[1].damping


def test_higher_delay_lowers_spring(tmp_path):
    p = tmp_path / "phys.physics3.json"
    _write_physics3(p, [
        {"Mobility": 0.5, "Delay": 0.1, "Acceleration": 1.0, "Radius": 1.0},
        {"Mobility": 0.5, "Delay": 0.9, "Acceleration": 1.0, "Radius": 1.0},
    ])
    rig = load_physics3(p)[0]
    assert rig.chain[0].spring > rig.chain[1].spring


def test_higher_acceleration_raises_spring(tmp_path):
    p = tmp_path / "phys.physics3.json"
    _write_physics3(p, [
        {"Mobility": 0.5, "Delay": 0.5, "Acceleration": 0.2, "Radius": 1.0},
        {"Mobility": 0.5, "Delay": 0.5, "Acceleration": 1.8, "Radius": 1.0},
    ])
    rig = load_physics3(p)[0]
    assert rig.chain[0].spring < rig.chain[1].spring


def test_higher_radius_raises_mass(tmp_path):
    p = tmp_path / "phys.physics3.json"
    _write_physics3(p, [
        {"Mobility": 0.5, "Delay": 0.5, "Acceleration": 1.0, "Radius": 0.2},
        {"Mobility": 0.5, "Delay": 0.5, "Acceleration": 1.0, "Radius": 2.0},
    ])
    rig = load_physics3(p)[0]
    assert rig.chain[0].mass < rig.chain[1].mass


def test_mapped_values_stay_within_safe_bounds(tmp_path):
    """Pathological Cubism values must not break our integrator —
    damping must stay strictly < 1, spring must stay positive."""
    p = tmp_path / "phys.physics3.json"
    _write_physics3(p, [
        {"Mobility": 1.0, "Delay": 1.0, "Acceleration": 0.0, "Radius": 0.0},
        {"Mobility": 0.0, "Delay": 0.0, "Acceleration": 10.0, "Radius": 100.0},
    ])
    rig = load_physics3(p)[0]
    for particle in rig.chain:
        assert 0.0 <= particle.damping < 1.0
        assert particle.spring > 0.0
        assert particle.mass > 0.0


def test_missing_vertex_fields_use_defaults(tmp_path):
    """A vertex with only the position field (no Mobility / Delay /
    Acceleration / Radius) shouldn't crash — the importer must fall
    back to the project default particle."""
    p = tmp_path / "phys.physics3.json"
    _write_physics3(p, [{"Position": {"X": 0, "Y": 0}}])
    rig = load_physics3(p)[0]
    assert len(rig.chain) == 1
    particle = rig.chain[0]
    assert 0.0 <= particle.damping < 1.0
    assert particle.spring > 0.0
