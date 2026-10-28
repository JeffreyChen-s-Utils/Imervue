"""Ordered codecs for required and optional puppet manifest collections."""
from __future__ import annotations

from Imervue.puppet.drawable_codec import _drawable_to_json, _parse_drawable
from Imervue.puppet.parameter_codec import (
    _parameter_blend_to_json,
    _parameter_to_json,
    _parse_parameter,
    _parse_parameter_blend,
)
from Imervue.puppet.rig_codec import (
    _deformer_to_json,
    _hit_area_to_json,
    _parse_deformer,
    _parse_hit_area,
    _parse_part,
    _part_to_json,
)

_REQUIRED_COLLECTIONS = (
    ("drawables", _parse_drawable, _drawable_to_json),
    ("deformers", _parse_deformer, _deformer_to_json),
    ("parameters", _parse_parameter, _parameter_to_json),
)


_OPTIONAL_COLLECTIONS = (
    ("hit_areas", _parse_hit_area, _hit_area_to_json),
    ("parameter_blends", _parse_parameter_blend, _parameter_blend_to_json),
    ("parts", _parse_part, _part_to_json),
)
