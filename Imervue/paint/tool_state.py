"""Paint tool state, public settings exports, persistence, and listeners."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from Imervue.paint.pressure_curve import PressureCurve
from Imervue.paint.rulers import Ruler
from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict
from Imervue.paint.tool_state_settings import (
    TOOLS,
    DEFAULT_TOOL,
    BRUSH_KINDS,
    DEFAULT_BRUSH_KIND,
    BLEND_MODES,
    DEFAULT_BLEND_MODE,
    BRUSH_SIZE_MIN,
    BRUSH_SIZE_MAX,
    BRUSH_OPACITY_MIN,
    BRUSH_OPACITY_MAX,
    BRUSH_HARDNESS_MIN,
    BRUSH_HARDNESS_MAX,
    BRUSH_DENSITY_MIN,
    BRUSH_DENSITY_MAX,
    COLOR_HISTORY_MAX,
    DEFAULT_FG,
    DEFAULT_BG,
    Color,
    EVENT_TOOL,
    EVENT_BRUSH,
    EVENT_COLOR,
    EVENT_HISTORY,
    EVENT_FILL,
    EVENT_SELECTION_MODE,
    EVENT_GRADIENT,
    EVENT_SYMMETRY,
    EVENT_RULER,
    EVENT_SUB_TOOL,
    EVENT_EYEDROPPER,
    EVENT_PRESSURE_CURVE,
    EVENT_PEN,
    FILL_TOLERANCE_MIN,
    FILL_TOLERANCE_MAX,
    FILL_EXPAND_MIN,
    FILL_EXPAND_MAX,
    FILL_GAP_CLOSE_MIN,
    FILL_GAP_CLOSE_MAX,
    SUB_TOOL_NAME_MAX_LEN,
    BrushSettings,
    FillSettings,
    SubTool,
)
from Imervue.paint.tool_state_colors import ColorStateMixin
from Imervue.paint.tool_state_history import ColorHistoryMixin
from Imervue.paint.tool_state_options import ToolOptionsMixin
from Imervue.paint.tool_state_gradient import GradientStateMixin
from Imervue.paint.tool_state_ruler import RulerStateMixin
from Imervue.paint.tool_state_brush_fill import BrushFillStateMixin
from Imervue.paint.tool_state_subtools import SubToolStateMixin
from Imervue.paint.tool_state_codec import state_to_dict, state_from_dict



__all__ = [
    "TOOLS",
    "DEFAULT_TOOL",
    "BRUSH_KINDS",
    "DEFAULT_BRUSH_KIND",
    "BLEND_MODES",
    "DEFAULT_BLEND_MODE",
    "BRUSH_SIZE_MIN",
    "BRUSH_SIZE_MAX",
    "BRUSH_OPACITY_MIN",
    "BRUSH_OPACITY_MAX",
    "BRUSH_HARDNESS_MIN",
    "BRUSH_HARDNESS_MAX",
    "BRUSH_DENSITY_MIN",
    "BRUSH_DENSITY_MAX",
    "COLOR_HISTORY_MAX",
    "DEFAULT_FG",
    "DEFAULT_BG",
    "Color",
    "EVENT_TOOL",
    "EVENT_BRUSH",
    "EVENT_COLOR",
    "EVENT_HISTORY",
    "EVENT_FILL",
    "EVENT_SELECTION_MODE",
    "EVENT_GRADIENT",
    "EVENT_SYMMETRY",
    "EVENT_RULER",
    "EVENT_SUB_TOOL",
    "EVENT_EYEDROPPER",
    "EVENT_PRESSURE_CURVE",
    "EVENT_PEN",
    "FILL_TOLERANCE_MIN",
    "FILL_TOLERANCE_MAX",
    "FILL_EXPAND_MIN",
    "FILL_EXPAND_MAX",
    "FILL_GAP_CLOSE_MIN",
    "FILL_GAP_CLOSE_MAX",
    "SUB_TOOL_NAME_MAX_LEN",
    "BrushSettings",
    "FillSettings",
    "SubTool",
    "ToolState",
    "load_tool_state",
    "reset_tool_state",
]

_STATE_KEY = "paint_state"


@dataclass
class ToolState(
    ColorStateMixin, ToolOptionsMixin, GradientStateMixin, RulerStateMixin,
    BrushFillStateMixin, SubToolStateMixin, ColorHistoryMixin,
):
    """Mutable tool state with synchronous persistence and ordered notifications."""

    tool: str = DEFAULT_TOOL
    foreground: tuple[int, int, int] | None = DEFAULT_FG
    background: tuple[int, int, int] | None = DEFAULT_BG
    brush: BrushSettings = field(default_factory=BrushSettings)
    fill: FillSettings = field(default_factory=FillSettings)
    selection_mode: str = "replace"
    gradient_kind: str = "linear"
    gradient_reverse: bool = False
    gradient_repeat: int = 1
    # Name of a saved multi-stop gradient (gradient_editor); "" = foreground → background.
    gradient_name: str = ""
    symmetry_mode: str = "off"
    ruler: Ruler = field(default_factory=Ruler)
    color_history: list[tuple[int, int, int]] = field(default_factory=list)
    # Lasso outlines snap to the strongest nearby edge (paint/magnetic_lasso).
    lasso_magnetic: bool = False
    # Palette the Swatches dock shows (paint/color_palette); "" = the recent colours.
    swatch_palette: str = ""
    # Pen paths run as one smooth curve through the anchors (paint/catmull_rom_spline).
    pen_smooth: bool = False
    snap_to_pixel: bool = False
    snap_to_edges: bool = False
    # When ``True`` and the workspace has a manga panel layout
    # registered, the brush clips strokes to the interior of the
    # panel containing the press point. Matches raster paint apps'
    # "コマ内描画制限" toggle. Default off so the existing brush
    # behaviour is unchanged.
    snap_to_panel: bool = False
    quick_mask_active: bool = False
    # When ``True`` the eyedropper samples from the document composite
    # (every visible layer flattened) instead of the active layer
    # only. Matches raster paint apps / PS's "Sample All Layers" eyedropper
    # toggle. False keeps the historical "active layer only" behaviour
    # so existing workflows are unchanged.
    eyedropper_sample_all_layers: bool = False
    # Tablet pen pressure passes through this curve before it scales the
    # brush size and opacity (Settings > Pressure Curve…). Identity by default.
    pressure_curve: PressureCurve = field(default_factory=PressureCurve)
    sub_tools: dict[str, list[SubTool]] = field(default_factory=dict)
    _listeners: list[Callable[[str], None]] = field(
        default_factory=list, repr=False, compare=False,
    )

    def subscribe(self, callback: Callable[[str], None]) -> Callable[[], None]:
        """Register a listener invoked with a channel name on each change.

        Returns an unsubscribe handle the caller can call to detach.
        """
        self._listeners.append(callback)

        def _unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)
        return _unsubscribe

    def _emit(self, channel: str) -> None:
        for cb in self._listeners.copy():
            cb(channel)

    def _persist(self) -> None:
        user_setting_dict[_STATE_KEY] = self.to_dict()
        schedule_save()

    def _publish(self, *channels: str) -> None:
        self._persist()
        for channel in channels:
            self._emit(channel)

    def _set_value(self, attribute: str, value: Any) -> bool:
        if value == getattr(self, attribute):
            return False
        setattr(self, attribute, value)
        return True

    def _set_converted(self, attribute: str, value: Any, convert: Callable) -> bool:
        if convert(value) == getattr(self, attribute):
            return False
        # Existing setters convert again on assignment; custom conversions may raise.
        setattr(self, attribute, convert(value))
        return True

    def _change_converted(
        self, attribute: str, value: Any, convert: Callable, channel: str,
    ) -> bool:
        if not self._set_converted(attribute, value, convert):
            return False
        self._publish(channel)
        return True

    def _change(self, attribute: str, value: Any, channel: str) -> bool:
        return self._change_converted(attribute, value, lambda item: item, channel)

    def to_dict(self) -> dict:
        """Return the persisted paint-state representation."""
        return state_to_dict(self)

    @classmethod
    def from_dict(cls, raw: dict | None) -> ToolState:
        """Build a state from a possibly-incomplete on-disk dict."""
        return state_from_dict(cls, raw)


_INSTANCE: ToolState | None = None


def load_tool_state() -> ToolState:
    """Return (and lazily build) the process-wide ``ToolState`` singleton."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ToolState.from_dict(user_setting_dict.get(_STATE_KEY))
    return _INSTANCE


def reset_tool_state() -> None:
    """Drop the cached singleton — used by tests to force re-load."""
    global _INSTANCE
    _INSTANCE = None
