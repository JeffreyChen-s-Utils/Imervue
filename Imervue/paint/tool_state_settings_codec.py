"""Encode and recover brush/fill snapshots with their stored field sets."""
from __future__ import annotations

from typing import Any

from Imervue.paint.tool_state_settings import (
    recover_choice, BrushSettings, FillSettings, BRUSH_KINDS, BLEND_MODES,
    DEFAULT_BRUSH_KIND, DEFAULT_BLEND_MODE,
)
from Imervue.paint.tool_state_normalize import _clamp_brush_attr, _clamp_fill_attr


def _brush_from_dict(raw: Any) -> BrushSettings:
    if not isinstance(raw, dict):
        return BrushSettings()
    kind = recover_choice(raw.get("kind"), BRUSH_KINDS, DEFAULT_BRUSH_KIND)
    blend = recover_choice(raw.get("blend_mode"), BLEND_MODES, DEFAULT_BLEND_MODE)
    return BrushSettings(
        kind=kind,
        size=_clamp_brush_attr("size", raw.get("size", 12)),
        opacity=_clamp_brush_attr("opacity", raw.get("opacity", 1.0)),
        hardness=_clamp_brush_attr("hardness", raw.get("hardness", 0.8)),
        density=_clamp_brush_attr("density", raw.get("density", 1.0)),
        blend_mode=blend,
        stabilizer=_clamp_brush_attr("stabilizer", raw.get("stabilizer", 0.0)),
        tip_path=_clamp_brush_attr("tip_path", raw.get("tip_path")),
        scatter=_clamp_brush_attr("scatter", raw.get("scatter", 0.0)),
        color_jitter=_clamp_brush_attr("color_jitter", raw.get("color_jitter", 0.0)),
        follow_tilt=_clamp_brush_attr("follow_tilt", raw.get("follow_tilt", False)),
    )


def _fill_from_dict(raw: Any) -> FillSettings:
    if not isinstance(raw, dict):
        return FillSettings()
    return FillSettings(
        tolerance=_clamp_fill_attr("tolerance", raw.get("tolerance", 32)),
        contiguous=bool(raw.get("contiguous", True)),
        sample_all_layers=bool(raw.get("sample_all_layers", False)),
        expand_px=_clamp_fill_attr("expand_px", raw.get("expand_px", 0)),
        use_reference_layer=bool(raw.get("use_reference_layer", False)),
        gap_close_px=_clamp_fill_attr("gap_close_px", raw.get("gap_close_px", 0)),
    )


_BRUSH_FIELDS = (
    "kind", "size", "opacity", "hardness", "density", "blend_mode", "stabilizer",
    "tip_path", "scatter", "color_jitter", "follow_tilt",
)
_FILL_FIELDS = (
    "tolerance", "contiguous", "sample_all_layers", "expand_px", "use_reference_layer",
    "gap_close_px",
)


def brush_to_dict(brush: BrushSettings) -> dict:
    """Encode the supported brush fields, preserving their stored order."""
    return {key: getattr(brush, key) for key in _BRUSH_FIELDS}


def fill_to_dict(fill: FillSettings, *, preset: bool = False) -> dict:
    """Encode fill settings; saved sub-tools historically omit gap closing."""
    keys = _FILL_FIELDS[:-1] if preset else _FILL_FIELDS
    return {key: getattr(fill, key) for key in keys}
