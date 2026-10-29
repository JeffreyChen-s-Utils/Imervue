"""Single-parameter and multi-parameter deformation bindings."""
from __future__ import annotations

from Imervue.puppet.document import (
    BlendKey,
    Parameter,
    ParameterBlend,
    ParameterKey,
)
from Imervue.puppet.format_values import PuppetFormatError, _require_keys


def _parse_parameter(raw: dict) -> Parameter:
    _require_keys(raw, ("id", "min", "max", "default"), "parameter")
    keys_raw = raw.get("keys", [])
    keys = [
        ParameterKey(
            value=float(k["value"]),
            forms={str(k_id): dict(form) for k_id, form in (k.get("forms") or {}).items()},
        )
        for k in keys_raw
    ]
    return Parameter(
        id=str(raw["id"]),
        min=float(raw["min"]),
        max=float(raw["max"]),
        default=float(raw["default"]),
        keys=keys,
    )


def _parameter_to_json(p: Parameter) -> dict:
    return {
        "id": p.id,
        "min": p.min,
        "max": p.max,
        "default": p.default,
        "keys": [
            {"value": k.value, "forms": {k_id: dict(form) for k_id, form in k.forms.items()}}
            for k in p.keys
        ],
    }


def _parse_parameter_blend(raw: dict) -> ParameterBlend:
    _require_keys(raw, ("id", "parameters", "keys"), "parameter blend")
    parameters = [str(p) for p in raw["parameters"]]
    if not parameters:
        raise PuppetFormatError(
            f"parameter blend {raw['id']!r} needs at least one parameter id",
        )
    keys: list[BlendKey] = []
    for k_idx, key_raw in enumerate(raw["keys"]):
        coords_raw = key_raw.get("coords")
        if not isinstance(coords_raw, list) or len(coords_raw) != len(parameters):
            raise PuppetFormatError(
                f"parameter blend {raw['id']!r} keys[{k_idx}].coords length "
                f"must match parameters length ({len(parameters)})",
            )
        forms_raw = key_raw.get("forms") or {}
        keys.append(
            BlendKey(
                coords=[float(c) for c in coords_raw],
                forms={str(d): dict(f) for d, f in forms_raw.items()},
            ),
        )
    return ParameterBlend(id=str(raw["id"]), parameters=parameters, keys=keys)


def _parameter_blend_to_json(b: ParameterBlend) -> dict:
    return {
        "id": b.id,
        "parameters": list(b.parameters),
        "keys": [
            {
                "coords": [float(c) for c in k.coords],
                "forms": {d: dict(f) for d, f in k.forms.items()},
            }
            for k in b.keys
        ],
    }
