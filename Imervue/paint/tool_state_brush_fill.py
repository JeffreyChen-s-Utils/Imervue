"""Apply atomic brush and fill snapshot changes."""
from __future__ import annotations

from typing import Any

from Imervue.paint.tool_state_settings import BRUSH_KINDS, BLEND_MODES, EVENT_BRUSH, EVENT_FILL
from Imervue.paint.tool_state_normalize import (
    replace_settings, _clamp_brush_attr, _clamp_fill_attr,
)


class BrushFillStateMixin:
    """Apply atomic brush and fill snapshot changes."""

    def set_fill(self, **kwargs: Any) -> bool:
        """Update fill bucket attributes."""
        new = replace_settings(self.fill, kwargs, _clamp_fill_attr, "fill")
        if new == self.fill:
            return False
        self.fill = new
        self._publish(EVENT_FILL)
        return True

    def set_brush(self, **kwargs: Any) -> bool:
        """Update one or more brush attributes at once.

        Unknown keys are rejected to avoid silent typos. Returns ``True``
        if any attribute actually changed.
        """
        new = replace_settings(self.brush, kwargs, _clamp_brush_attr, "brush")
        if new == self.brush:
            return False
        if new.kind not in BRUSH_KINDS:
            raise ValueError(
                f"unknown brush kind {new.kind!r}; expected one of {BRUSH_KINDS}",
            )
        if new.blend_mode not in BLEND_MODES:
            raise ValueError(
                f"unknown blend mode {new.blend_mode!r}; expected one of {BLEND_MODES}",
            )
        self.brush = new
        self._publish(EVENT_BRUSH)
        return True
