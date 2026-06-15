"""Browsing-history (Alt+←/→) controller for :class:`GPUImageView`.

Owns the history stack, current position, and the navigating flag so the
view keeps only thin ``history_back`` / ``history_forward`` / ``_push_history``
forwarders. Navigation loads images through the view but suppresses the
re-push so the back/forward buttons mirror browser semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_HISTORY_MAX = 200


class HistoryController:
    """Track and navigate the deep-zoom browsing history."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view
        self._history: list[str] = []
        self._pos: int = -1
        self._navigating: bool = False

    def push(self, path: str) -> None:
        """Append a new image to the history unless we're navigating.

        If the user is in the middle of history (has gone back) and picks a
        new image manually, that truncates the forward entries — matches
        browser behaviour and avoids a broken forward button.
        """
        if self._navigating or not path:
            return
        # Deduplicate adjacent entries (reloads shouldn't double-push).
        if self._history and self._pos >= 0 and self._history[self._pos] == path:
            return
        # Drop forward history when branching.
        if self._pos < len(self._history) - 1:
            del self._history[self._pos + 1:]
        self._history.append(path)
        # Cap size.
        if len(self._history) > _HISTORY_MAX:
            overflow = len(self._history) - _HISTORY_MAX
            del self._history[:overflow]
        self._pos = len(self._history) - 1

    def back(self) -> bool:
        """Jump to the previous image in history. Returns True on success."""
        if self._pos <= 0:
            return False
        self._pos -= 1
        self._navigate()
        return True

    def forward(self) -> bool:
        """Jump to the next image in history. Returns True on success."""
        if self._pos >= len(self._history) - 1:
            return False
        self._pos += 1
        self._navigate()
        return True

    def _navigate(self) -> None:
        """Load the image at ``_pos`` without re-pushing to the stack."""
        view = self._view
        path = self._history[self._pos]
        if not Path(path).is_file():
            return
        images = view.model.images
        if path in images:
            view.current_index = images.index(path)
        self._navigating = True
        try:
            view._clear_deep_zoom()
            view.tile_grid_mode = False
            view.load_deep_zoom_image(path)
        finally:
            self._navigating = False
