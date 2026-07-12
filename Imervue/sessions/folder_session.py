"""Pure helpers for per-folder view-session save / restore.

The main window persists a small dict per browsed folder (browse mode, current
image, selection, and whether it was last viewed in deep zoom). Keeping the
restore *decisions* here — free of Qt and the main window — makes them unit-
testable without building the GL-backed viewer.
"""
from __future__ import annotations

from typing import Any


def deep_zoom_restore_target(
    state: dict[str, Any], images: list[str], current_index: int,
) -> str | None:
    """Return the image to reopen in deep zoom on restore, or ``None``.

    Only when the session recorded ``deep_zoom`` and the remembered current
    index still points at a live image. ``None`` (stay on the tile wall) when
    the flag is unset, the folder is empty, or the index is out of range —
    e.g. the image was deleted between sessions.
    """
    if not state.get("deep_zoom"):
        return None
    if images and 0 <= current_index < len(images):
        return images[current_index]
    return None
