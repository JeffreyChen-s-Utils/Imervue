"""Encode whole tool state and recover defaults from persisted settings."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from Imervue.paint.pressure_curve import PressureCurve
from Imervue.paint.rulers import Ruler
from Imervue.paint.tool_state_settings import (
    TOOLS, DEFAULT_TOOL, DEFAULT_FG, DEFAULT_BG, recover_choice,
)
from Imervue.paint.tool_state_color_values import _safe_color
from Imervue.paint.tool_state_history import _history_from_list
from Imervue.paint.tool_state_settings_codec import (
    _brush_from_dict, _fill_from_dict, brush_to_dict, fill_to_dict,
)
from Imervue.paint.tool_state_subtool_codec import _sub_tool_to_dict, _sub_tools_from_dict

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


def state_to_dict(self) -> dict:
    return {
        "tool": self.tool,
        "foreground": (
            list(self.foreground) if self.foreground is not None else None
        ),
        "background": (
            list(self.background) if self.background is not None else None
        ),
        "brush": brush_to_dict(self.brush),
        "fill": fill_to_dict(self.fill),
        "selection_mode": self.selection_mode,
        "lasso_magnetic": bool(self.lasso_magnetic),
        "swatch_palette": self.swatch_palette,
        "pen_smooth": bool(self.pen_smooth),
        "gradient_kind": self.gradient_kind,
        "gradient_reverse": self.gradient_reverse,
        "gradient_repeat": self.gradient_repeat,
        "gradient_name": self.gradient_name,
        "symmetry_mode": self.symmetry_mode,
        "ruler": self.ruler.to_dict(),
        "color_history": [list(c) for c in self.color_history],
        "snap_to_pixel": bool(self.snap_to_pixel),
        "snap_to_edges": bool(self.snap_to_edges),
        "snap_to_panel": bool(self.snap_to_panel),
        "quick_mask_active": bool(self.quick_mask_active),
        "eyedropper_sample_all_layers": bool(self.eyedropper_sample_all_layers),
        "pressure_curve": self.pressure_curve.to_dict(),
        "sub_tools": {
            tool: [_sub_tool_to_dict(st) for st in entries]
            for tool, entries in self.sub_tools.items()
        },
    }


def state_from_dict(cls, raw: dict | None) -> ToolState:
    """Build a state from a possibly-incomplete on-disk dict."""
    raw = raw if isinstance(raw, dict) else {}
    tool = recover_choice(raw.get("tool"), TOOLS, DEFAULT_TOOL)
    fg = _safe_color(
        raw.get("foreground", DEFAULT_FG), DEFAULT_FG,
    )
    bg = _safe_color(
        raw.get("background", DEFAULT_BG), DEFAULT_BG,
    )
    brush = _brush_from_dict(raw.get("brush"))
    fill = _fill_from_dict(raw.get("fill"))
    selection_mode = raw.get("selection_mode", "replace")
    from Imervue.paint.selection import SELECTION_MODES
    selection_mode = recover_choice(selection_mode, SELECTION_MODES, "replace")
    from Imervue.paint.gradient import GRADIENT_KINDS
    gradient_kind = raw.get("gradient_kind", "linear")
    gradient_kind = recover_choice(gradient_kind, GRADIENT_KINDS, "linear")
    gradient_reverse = bool(raw.get("gradient_reverse", False))
    try:
        gradient_repeat = max(1, int(raw.get("gradient_repeat", 1)))
    except (TypeError, ValueError):
        gradient_repeat = 1
    from Imervue.paint.symmetry import DEFAULT_SYMMETRY_MODE, SYMMETRY_MODES
    symmetry_mode = raw.get("symmetry_mode", DEFAULT_SYMMETRY_MODE)
    symmetry_mode = recover_choice(symmetry_mode, SYMMETRY_MODES, DEFAULT_SYMMETRY_MODE)
    ruler = Ruler.from_dict(raw.get("ruler"))
    history = _history_from_list(raw.get("color_history"))
    sub_tools = _sub_tools_from_dict(raw.get("sub_tools"))
    return cls(
        tool=tool, foreground=fg, background=bg,
        brush=brush, fill=fill, selection_mode=selection_mode,
        lasso_magnetic=bool(raw.get("lasso_magnetic", False)),
        swatch_palette=str(raw.get("swatch_palette", "") or ""),
        pen_smooth=bool(raw.get("pen_smooth", False)),
        gradient_kind=gradient_kind, gradient_reverse=gradient_reverse,
        gradient_repeat=gradient_repeat,
        gradient_name=str(raw.get("gradient_name", "") or ""),
        symmetry_mode=symmetry_mode, ruler=ruler,
        color_history=history,
        snap_to_pixel=bool(raw.get("snap_to_pixel", False)),
        snap_to_edges=bool(raw.get("snap_to_edges", False)),
        snap_to_panel=bool(raw.get("snap_to_panel", False)),
        quick_mask_active=bool(raw.get("quick_mask_active", False)),
        eyedropper_sample_all_layers=bool(
            raw.get("eyedropper_sample_all_layers", False),
        ),
        pressure_curve=_pressure_curve_from_dict(raw.get("pressure_curve")),
        sub_tools=sub_tools,
    )


def _pressure_curve_from_dict(raw: Any) -> PressureCurve:
    """The saved curve, or the identity when it is missing or malformed."""
    if raw is None:
        return PressureCurve()
    try:
        return PressureCurve.from_dict(raw)
    except ValueError:
        return PressureCurve()
