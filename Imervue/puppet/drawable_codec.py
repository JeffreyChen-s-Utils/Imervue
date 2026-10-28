"""Puppet drawable geometry, deforming curves and JSON representation."""
from __future__ import annotations

from Imervue.puppet.document import BLEND_MODES, Drawable
from Imervue.puppet.drawable_curves import (
    _keys_to_json,
    _parse_alpha_stop,
    _parse_color3,
    _parse_color_stop,
    _parse_keys,
)
from Imervue.puppet.drawable_deformation import (
    _bone_weights_to_json,
    _morphs_to_json,
    _parse_bone_weights,
    _parse_vertex_morphs,
)
from Imervue.puppet.format_values import PuppetFormatError, _require_keys


def _parse_drawable(raw: dict) -> Drawable:
    _require_keys(raw, ("id", "texture", "vertices", "indices", "uvs", "draw_order"), "drawable")
    blend = raw.get("blend_mode", "normal")
    if blend not in BLEND_MODES:
        raise PuppetFormatError(f"drawable {raw['id']!r} blend_mode {blend!r} not in {BLEND_MODES}")
    indices = [int(i) for i in raw["indices"]]
    if len(indices) % 3 != 0:
        raise PuppetFormatError(
            f"drawable {raw['id']!r} indices length {len(indices)} not divisible by 3"
        )
    if len(raw["vertices"]) != len(raw["uvs"]):
        raise PuppetFormatError(
            f"drawable {raw['id']!r} vertices/uvs length mismatch"
        )
    n_vertices = len(raw["vertices"])
    if any(not 0 <= i < n_vertices for i in indices):
        # An index past the vertex count would be handed straight to
        # glDrawElements and read past the end of the vertex VBO — undefined
        # GPU behaviour ranging from garbage geometry to a driver reset. Reject
        # it at load time instead.
        raise PuppetFormatError(
            f"drawable {raw['id']!r} has a triangle index outside "
            f"[0, {n_vertices})"
        )
    bone_weights = _parse_bone_weights(
        raw.get("bone_weights"), len(raw["vertices"]), raw["id"],
    )
    opacity_keys = _parse_keys(
        raw.get("opacity_keys"), raw["id"], "opacity_keys", _parse_alpha_stop,
    )
    multiply_color = _parse_color3(raw.get("multiply_color"), default=(1.0, 1.0, 1.0))
    multiply_color_keys = _parse_keys(
        raw.get("multiply_color_keys"), raw["id"], "multiply_color_keys", _parse_color_stop,
    )
    vertex_morphs = _parse_vertex_morphs(raw.get("vertex_morphs"), raw["id"])
    return Drawable(
        id=str(raw["id"]),
        texture=str(raw["texture"]),
        vertices=[(float(x), float(y)) for x, y in raw["vertices"]],
        indices=[int(i) for i in indices],
        uvs=[(float(u), float(v)) for u, v in raw["uvs"]],
        draw_order=int(raw["draw_order"]),
        blend_mode=blend,
        clip_mask=raw.get("clip_mask"),
        visible=bool(raw.get("visible", True)),
        opacity=float(raw.get("opacity", 1.0)),
        bone_weights=bone_weights,
        opacity_keys=opacity_keys,
        multiply_color=multiply_color,
        multiply_color_keys=multiply_color_keys,
        vertex_morphs=vertex_morphs,
    )


def _drawable_to_json(d: Drawable) -> dict:
    out = {
        "id": d.id,
        "texture": d.texture,
        "vertices": [list(v) for v in d.vertices],
        "indices": list(d.indices),
        "uvs": [list(uv) for uv in d.uvs],
        "draw_order": d.draw_order,
        "blend_mode": d.blend_mode,
        "visible": d.visible,
        "opacity": d.opacity,
    }
    if d.clip_mask is not None:
        out["clip_mask"] = d.clip_mask
    if d.bone_weights:
        out["bone_weights"] = _bone_weights_to_json(d.bone_weights)
    if d.opacity_keys:
        out["opacity_keys"] = _keys_to_json(d.opacity_keys, "alpha", float)
    if d.multiply_color != (1.0, 1.0, 1.0):
        out["multiply_color"] = list(d.multiply_color)
    if d.multiply_color_keys:
        out["multiply_color_keys"] = _keys_to_json(d.multiply_color_keys, "color", list)
    if d.vertex_morphs:
        out["vertex_morphs"] = _morphs_to_json(d.vertex_morphs)
    return out


