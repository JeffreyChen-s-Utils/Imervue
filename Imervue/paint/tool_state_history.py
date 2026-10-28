"""Maintain recent-color order and decode its persisted representation."""
from __future__ import annotations

from typing import Any

from Imervue.paint.tool_state_color_values import _safe_rgb
from Imervue.paint.tool_state_settings import COLOR_HISTORY_MAX, EVENT_HISTORY


class ColorHistoryMixin:
    """Record painted colors and publish recent-color changes."""

    def record_foreground_in_history(self) -> None:
        """Push the current foreground onto the recents stack without
        otherwise changing state. Called by the brush dispatcher when
        a stroke begins so "recents" reflects colours actually used
        for paint. ``None`` (transparent) is skipped — there's no
        opaque colour to recall."""
        if self.foreground is None:
            return
        self._push_color_history(self.foreground)
        self._publish(EVENT_HISTORY)


    def _push_color_history(self, rgb: tuple[int, int, int]) -> None:
        if rgb in self.color_history:
            self.color_history.remove(rgb)
        self.color_history.insert(0, rgb)
        del self.color_history[COLOR_HISTORY_MAX:]


    def clear_color_history(self) -> None:
        if not self.color_history:
            return
        self.color_history.clear()
        self._publish(EVENT_HISTORY)



def _history_from_list(raw: Any) -> list[tuple[int, int, int]]:
    if not isinstance(raw, list):
        return []
    out: list[tuple[int, int, int]] = []
    for entry in raw:
        color = _safe_rgb(entry, None)
        if color is not None:
            out.append(color)
        if len(out) >= COLOR_HISTORY_MAX:
            break
    return out
