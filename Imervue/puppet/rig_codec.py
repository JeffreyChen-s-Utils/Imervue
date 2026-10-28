"""Puppet rig structure, parameter bindings and interaction metadata."""
from __future__ import annotations

from Imervue.puppet.document import (
    DEFORMER_TYPES,
    Deformer,
    HitArea,
    Part,
    PoseGroup,
)
from Imervue.puppet.format_values import PuppetFormatError, _require_keys


def _parse_deformer(raw: dict) -> Deformer:
    _require_keys(raw, ("id", "type", "drawables", "form"), "deformer")
    if raw["type"] not in DEFORMER_TYPES:
        raise PuppetFormatError(
            f"deformer {raw['id']!r} type {raw['type']!r} not in {DEFORMER_TYPES}"
        )
    return Deformer(
        id=str(raw["id"]),
        type=raw["type"],
        parent=raw.get("parent"),
        drawables=[str(d) for d in raw["drawables"]],
        form=dict(raw["form"]),
    )


def _parse_pose_group(raw: dict) -> PoseGroup:
    _require_keys(raw, ("id", "drawables"), "pose group")
    return PoseGroup(
        id=str(raw["id"]),
        drawables=[str(d) for d in raw["drawables"]],
    )


def _deformer_to_json(d: Deformer) -> dict:
    return {
        "id": d.id,
        "type": d.type,
        "parent": d.parent,
        "drawables": list(d.drawables),
        "form": dict(d.form),
    }


def _pose_to_json(g: PoseGroup) -> dict:
    return {"id": g.id, "drawables": list(g.drawables)}


def _parse_hit_area(raw: dict) -> HitArea:
    _require_keys(raw, ("id", "drawables"), "hit area")
    return HitArea(
        id=str(raw["id"]),
        drawables=[str(d) for d in raw["drawables"]],
        motion=str(raw["motion"]) if raw.get("motion") else None,
        expression=str(raw["expression"]) if raw.get("expression") else None,
    )


def _hit_area_to_json(h: HitArea) -> dict:
    out: dict = {"id": h.id, "drawables": list(h.drawables)}
    if h.motion is not None:
        out["motion"] = h.motion
    if h.expression is not None:
        out["expression"] = h.expression
    return out


def _parse_part(raw: dict) -> Part:
    _require_keys(raw, ("id",), "part")
    return Part(
        id=str(raw["id"]),
        drawables=[str(d) for d in raw.get("drawables") or []],
        children=[str(c) for c in raw.get("children") or []],
        visible=bool(raw.get("visible", True)),
        opacity=float(raw.get("opacity", 1.0)),
    )


def _part_to_json(p: Part) -> dict:
    return {
        "id": p.id,
        "drawables": list(p.drawables),
        "children": list(p.children),
        "visible": p.visible,
        "opacity": p.opacity,
    }


