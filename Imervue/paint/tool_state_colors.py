"""Edit foreground/background colors and publish recent-color history."""
from __future__ import annotations

from Imervue.paint.tool_state_settings import (
    DEFAULT_FG, DEFAULT_BG, EVENT_COLOR, EVENT_HISTORY,
)
from Imervue.paint.tool_state_color_values import _clamp_color


class ColorStateMixin:
    """Edit foreground/background colors and publish recent-color history."""

    def set_foreground(
        self,
        rgb: tuple[int, int, int] | None,
        *,
        commit: bool = False,
    ) -> bool:
        """Set the active foreground colour.

        ``rgb`` may be a 3-tuple of 0..255 ints or ``None`` to mark
        the foreground as "transparent / no colour". A transparent
        foreground turns the brush tool into a no-op (paint deposits
        nothing) so the user can pick "no colour" without first
        switching to the eraser.

        ``commit=True`` also records the colour in the recents history.
        Default is ``False`` so live-preview adjustments (slider drags,
        wheel scrolls) don't pollute "recently used" with every
        intermediate value — only colours the user actually paints
        with, picks via the colour dialog, or clicks from a swatch
        should land in recents. The transparent value is never pushed
        to history (recents are for *colours*).
        """
        rgb = _clamp_color(rgb)
        if rgb == self.foreground:
            if commit and rgb is not None:
                self._push_color_history(rgb)
                self._publish(EVENT_HISTORY)
            return False
        self.foreground = rgb
        if commit and rgb is not None:
            self._push_color_history(rgb)
        self._publish(EVENT_COLOR)
        if commit and rgb is not None:
            self._emit(EVENT_HISTORY)
        return True


    def set_background(self, rgb: tuple[int, int, int] | None) -> bool:
        rgb = _clamp_color(rgb)
        return self._change("background", rgb, EVENT_COLOR)

    def swap_colors(self) -> None:
        """Exchange foreground and background — raster paint apps' X shortcut."""
        if self.foreground == self.background:
            return
        self.foreground, self.background = self.background, self.foreground
        self._publish(EVENT_COLOR)

    def reset_colors(self) -> None:
        """Reset to black/white — raster paint apps' D shortcut."""
        if (self.foreground, self.background) != (DEFAULT_FG, DEFAULT_BG):
            self.foreground, self.background = DEFAULT_FG, DEFAULT_BG
            self._publish(EVENT_COLOR)
