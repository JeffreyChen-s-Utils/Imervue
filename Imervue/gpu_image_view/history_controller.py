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
        if not self._navigate():
            self._pos += 1  # target unreachable — don't strand the pointer
            return False
        return True

    def forward(self) -> bool:
        """Jump to the next image in history. Returns True on success."""
        if self._pos >= len(self._history) - 1:
            return False
        self._pos += 1
        if not self._navigate():
            self._pos -= 1
            return False
        return True

    def _navigate(self) -> bool:
        """Load the image at ``_pos`` without re-pushing to the stack.

        Returns True once it has loaded / reopened the target, False when the
        entry is unreachable (the file was deleted) so the caller can roll the
        position back instead of silently consuming a step onto a dead entry.
        """
        view = self._view
        path = self._history[self._pos]
        if not Path(path).is_file():
            return False
        images = view.model.images
        self._navigating = True
        try:
            if path in images:
                view.current_index = images.index(path)
                # Save the outgoing image's zoom/pan before the clear nulls the
                # key, so Alt+Left then Alt+Right returns to where you left off.
                view._save_view_state()
                view._clear_deep_zoom()
                view.tile_grid_mode = False
                view.load_deep_zoom_image(path)
            else:
                self._open_cross_folder(path)
        finally:
            self._navigating = False
        return True

    def _open_cross_folder(self, path: str) -> None:
        """Show a history image that has left the current folder's list.

        History spans folders, so back/forward can target an image that is no
        longer a row in ``model.images`` — a different folder, or one since
        filtered or removed. Loading it directly would strand a "Loading…" view
        that the deep-zoom completion guard discards (it isn't in the list, so
        there is no row to anchor it to). Route through the main window instead
        so the image's own folder is reopened and it displays in context. Fall
        back to a direct load when no main window is wired (a detached or test
        view), which preserves the previous behaviour there.
        """
        view = self._view
        navigate = getattr(getattr(view, "main_window", None),
                           "navigate_to_path", None)
        if callable(navigate):
            navigate(path)
            return
        view._clear_deep_zoom()
        view.tile_grid_mode = False
        view.load_deep_zoom_image(path)
