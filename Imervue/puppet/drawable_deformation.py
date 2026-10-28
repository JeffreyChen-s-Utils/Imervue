"""Vertex deformation weights and morph endpoint data."""
from __future__ import annotations

from typing import Any

from Imervue.puppet.format_values import PuppetFormatError, _parameter_name


def _parse_bone_weights(
    raw: Any, n_vertices: int, drawable_id: str,
) -> dict[str, list[float]] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PuppetFormatError(
            f"drawable {drawable_id!r} bone_weights must be a dict, got {type(raw).__name__}"
        )
    out: dict[str, list[float]] = {}
    for bone_id, weights in raw.items():
        if not isinstance(weights, list):
            raise PuppetFormatError(
                f"drawable {drawable_id!r} bone_weights[{bone_id!r}] must be a list"
            )
        if len(weights) != n_vertices:
            raise PuppetFormatError(
                f"drawable {drawable_id!r} bone_weights[{bone_id!r}] length "
                f"{len(weights)} does not match vertex count {n_vertices}"
            )
        out[str(bone_id)] = [float(w) for w in weights]
    return out


def _parse_vertex_morphs(raw: Any, drawable_id: str) -> list[dict] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise PuppetFormatError(
            f"drawable {drawable_id!r} vertex_morphs must be a list",
        )
    out: list[dict] = []
    for idx, entry in enumerate(raw):
        param = _parameter_name(entry, f"drawable {drawable_id!r} vertex_morphs[{idx}]")
        out.append({
            "parameter": param,
            **_morph_deltas(entry, tuple),
        })
    return out


def _morph_deltas(entry: dict, point_type: type[list] | type[tuple]) -> dict:
    return {
        key: [point_type((float(dx), float(dy))) for dx, dy in entry.get(key) or []]
        for key in ("delta_at_min", "delta_at_max")
    }


def _morphs_to_json(morphs: list[dict]) -> list[dict]:
    return [{"parameter": entry["parameter"], **_morph_deltas(entry, list)} for entry in morphs]


def _bone_weights_to_json(weights: dict[str, list[float]]) -> dict[str, list[float]]:
    return {bone_id: [float(w) for w in values] for bone_id, values in weights.items()}
