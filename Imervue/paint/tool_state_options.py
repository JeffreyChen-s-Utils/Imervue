"""Select tools, modes, and ordinary per-tool options."""
from __future__ import annotations

from Imervue.paint.pressure_curve import PressureCurve
from Imervue.paint.tool_state_settings import (
    validate_choice, TOOLS, EVENT_TOOL, EVENT_SYMMETRY, EVENT_SELECTION_MODE, EVENT_HISTORY,
    EVENT_PEN, EVENT_BRUSH, EVENT_EYEDROPPER, EVENT_PRESSURE_CURVE,
)


class ToolOptionsMixin:
    """Select tools, modes, and ordinary per-tool options."""

    def set_tool(self, tool: str) -> bool:
        """Switch the active tool. Returns ``True`` if it changed."""
        validate_choice(tool, TOOLS, "tool")
        return self._change("tool", tool, EVENT_TOOL)

    def set_symmetry_mode(self, mode: str) -> bool:
        """Switch the active brush symmetry mirror mode."""
        from Imervue.paint.symmetry import SYMMETRY_MODES
        validate_choice(mode, SYMMETRY_MODES, "symmetry mode")
        return self._change("symmetry_mode", mode, EVENT_SYMMETRY)

    def set_selection_mode(self, mode: str) -> bool:
        """Switch the active selection combine mode."""
        from Imervue.paint.selection import SELECTION_MODES
        validate_choice(mode, SELECTION_MODES, "selection mode")
        return self._change("selection_mode", mode, EVENT_SELECTION_MODE)

    def set_swatch_palette(self, name: str) -> bool:
        """Show the named palette in the Swatches dock (``""`` = recent). True if changed."""
        return self._change_converted("swatch_palette", name, str, EVENT_HISTORY)

    def set_pen_smooth(self, enabled: bool) -> bool:
        """Turn the pen's Smooth curve on or off. True if it changed."""
        return self._change_converted("pen_smooth", enabled, bool, EVENT_PEN)

    def set_snap_to_panel(self, enabled: bool) -> bool:
        """Keep brush strokes inside the manga panel they start in, or not. True if it changed."""
        return self._change_converted("snap_to_panel", enabled, bool, EVENT_BRUSH)

    def set_lasso_magnetic(self, enabled: bool) -> bool:
        """Turn edge snapping of lasso outlines on or off. True if it changed."""
        return self._change_converted("lasso_magnetic", enabled, bool, EVENT_SELECTION_MODE)

    def set_eyedropper_sample_all_layers(self, enabled: bool) -> bool:
        """Toggle whether the eyedropper samples the composite vs active.

        Returns ``True`` if the flag changed; emits ``EVENT_EYEDROPPER``
        so listening dock panels refresh their checkbox state.
        """
        return self._change("eyedropper_sample_all_layers", bool(enabled), EVENT_EYEDROPPER)

    def set_pressure_curve(self, curve: PressureCurve) -> bool:
        """Replace the tablet pressure curve; ``True`` when it changed."""
        return self._change("pressure_curve", curve, EVENT_PRESSURE_CURVE)
