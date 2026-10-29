"""Encode named sub-tools and discard malformed stored presets."""
from __future__ import annotations

from typing import Any

from Imervue.paint.tool_state_settings import TOOLS, SubTool
from Imervue.paint.tool_state_settings_codec import (
    _brush_from_dict, _fill_from_dict, brush_to_dict, fill_to_dict,
)


def _sub_tool_to_dict(sub_tool: SubTool) -> dict:
    return {
        "name": str(sub_tool.name),
        "brush": brush_to_dict(sub_tool.brush),
        "fill": fill_to_dict(sub_tool.fill, preset=True),
    }


def _sub_tools_from_dict(raw: Any) -> dict[str, list[SubTool]]:
    """Re-hydrate a saved ``sub_tools`` dict, dropping malformed entries."""
    out: dict[str, list[SubTool]] = {}
    if not isinstance(raw, dict):
        return out
    for tool, entries in raw.items():
        if tool not in TOOLS or not isinstance(entries, list):
            continue
        bucket: list[SubTool] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                bucket.append(SubTool(
                    name=str(entry.get("name", "")),
                    brush=_brush_from_dict(entry.get("brush")),
                    fill=_fill_from_dict(entry.get("fill")),
                ))
            except (TypeError, ValueError):
                continue
        if bucket:
            out[tool] = bucket
    return out
