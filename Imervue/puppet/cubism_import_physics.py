"""Cubism ``.physics3.json`` importer: each physics setting becomes a
:class:`PhysicsRig` whose particle chain maps the Cubism vertex
coefficients onto our spring / damping / mass dynamics."""
from __future__ import annotations

from pathlib import Path

from Imervue.puppet.cubism_import_common import _read_json
from Imervue.puppet.document import PhysicsParticle, PhysicsRig


def load_physics3(path: str | Path) -> list[PhysicsRig]:
    """Parse a Cubism ``.physics3.json`` into a list of
    :class:`PhysicsRig`.

    Cubism describes physics in much greater detail than our runtime
    (per-vertex Mobility / Delay / Acceleration / Radius, multiple
    Input/Output mappings, Normalization curves). We translate the
    shape rather than the dynamics: chain length comes from the
    Vertices array; the first ``Input.Source.Id`` and
    ``Output.Destination.Id`` become the rig's input/output params;
    each :class:`PhysicsParticle` uses our standard defaults. The
    result swings — just not pixel-identical to Cubism's runtime."""
    raw = _read_json(Path(path))
    settings = raw.get("PhysicsSettings") or []
    return [
        rig
        for entry in settings
        if (rig := _parse_physics_setting(entry)) is not None
    ]


def _parse_physics_setting(entry: dict) -> PhysicsRig | None:
    rig_id = entry.get("Id")
    inputs = entry.get("Input") or []
    outputs = entry.get("Output") or []
    vertices = entry.get("Vertices") or []
    if not isinstance(rig_id, str) or not inputs or not outputs or not vertices:
        return None
    input_param = _physics_endpoint_id(inputs[0], "Source")
    output_param = _physics_endpoint_id(outputs[0], "Destination")
    if input_param is None or output_param is None:
        return None
    return PhysicsRig(
        id=rig_id,
        input_param=input_param,
        output_param=output_param,
        chain=[_cubism_vertex_to_particle(v) for v in vertices],
    )


_DEFAULT_SPRING: float = 12.0


def _cubism_vertex_to_particle(vertex: dict) -> PhysicsParticle:
    """Map a Cubism physics vertex onto our particle dynamics.

    Cubism describes each vertex with four scalar coefficients:

    * ``Mobility`` ``[0, 1]`` — how much the particle responds to forces;
      we map this inversely onto damping (high mobility = low damping).
    * ``Delay`` ``[0, 1]`` — how slowly the particle catches up to its
      parent; we map this inversely onto spring stiffness (high delay =
      low spring, so the particle takes longer to converge).
    * ``Acceleration`` (non-negative) — boosts the spring on top of the
      delay-derived baseline so a heavy chain still has perceptible
      response.
    * ``Radius`` — rest distance from the parent vertex. We don't model
      per-particle radius in our Verlet integrator (all springs share
      ``REST_LENGTH``), but it influences ``mass``: bigger radius
      reads as a heavier inertia element.

    The mapping is a heuristic, not a faithful port of Cubism's
    proprietary integrator — but it captures the per-particle
    variation rather than collapsing everyone to the defaults."""
    mobility = _clamp01(vertex.get("Mobility", 1.0))
    delay = _clamp01(vertex.get("Delay", 1.0))
    acceleration = max(0.0, float(vertex.get("Acceleration", 1.0)))
    radius = max(0.0, float(vertex.get("Radius", 1.0)))
    damping = max(0.0, min(0.999, 1.0 - mobility * 0.9))
    spring = _DEFAULT_SPRING * (1.0 - delay * 0.8) * (0.5 + acceleration * 0.5)
    spring = max(0.5, min(30.0, spring))
    mass = max(0.25, min(4.0, 0.5 + radius * 0.5))
    return PhysicsParticle(mass=mass, damping=damping, spring=spring)


def _clamp01(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, v))


def _physics_endpoint_id(entry: dict, key: str) -> str | None:
    target = entry.get(key)
    if not isinstance(target, dict):
        return None
    if target.get("Target") != "Parameter":
        return None
    raw_id = target.get("Id")
    return str(raw_id) if isinstance(raw_id, str) else None
