"""Physics particle rigs and physics-file JSON representation."""
from __future__ import annotations

from Imervue.puppet.document import SCHEMA_VERSION, PhysicsParticle, PhysicsRig
from Imervue.puppet.format_schema import SCHEMA_FIELD, SCHEMA_URLS
from Imervue.puppet.format_values import _dumps, _require_keys


def _parse_physics_rig(raw: dict) -> PhysicsRig:
    _require_keys(raw, ("id", "input_param", "output_param", "chain"), "physics rig")
    chain = [
        PhysicsParticle(
            mass=float(p.get("mass", 1.0)),
            damping=float(p.get("damping", 0.7)),
            spring=float(p.get("spring", 12.0)),
        )
        for p in raw["chain"]
    ]
    gravity = raw.get("gravity", [0.0, -9.8])
    return PhysicsRig(
        id=str(raw["id"]),
        input_param=str(raw["input_param"]),
        output_param=str(raw["output_param"]),
        chain=chain,
        gravity=(float(gravity[0]), float(gravity[1])),
    )


def _physics_json_bytes(rigs: list[PhysicsRig]) -> bytes:
    payload = {
        SCHEMA_FIELD: SCHEMA_URLS["physics"],
        "version": SCHEMA_VERSION,
        "rigs": [
            {
                "id": r.id,
                "input_param": r.input_param,
                "output_param": r.output_param,
                "chain": [
                    {"mass": p.mass, "damping": p.damping, "spring": p.spring}
                    for p in r.chain
                ],
                "gravity": list(r.gravity),
            }
            for r in rigs
        ],
    }
    return _dumps(payload)
