"""Pure helpers for per-folder view-session save / restore.

The main window persists a small dict per browsed folder (browse mode, current
image, selection, and whether it was last viewed in deep zoom). Keeping the
restore *decisions* here — free of Qt and the main window — makes them unit-
testable without building the GL-backed viewer.
"""
from __future__ import annotations

from typing import Any


def deep_zoom_restore_target(state: dict[str, Any], images: list[str]) -> str | None:
    """Return the image to reopen in deep zoom, or ``None``.

    Only when the session recorded ``deep_zoom`` and the remembered current
    image is present in *images*. ``None`` when the flag is unset, no current
    image was stored, or it isn't in the (possibly still-loading) list yet.
    """
    if not state.get("deep_zoom"):
        return None
    current = state.get("current") or ""
    return current if current and current in images else None


def should_retry_deep_zoom_restore(state: dict[str, Any], images: list[str]) -> bool:
    """Whether to wait and retry the deep-zoom restore.

    The folder scan populates ``images`` asynchronously, so a restore that runs
    before the target lands would give up too early and drop the user on the
    tile wall. Retry while the session wants deep zoom, a target was recorded,
    and it hasn't appeared yet — the caller bounds the number of retries so a
    since-deleted image can't loop forever.
    """
    if not state.get("deep_zoom"):
        return False
    current = state.get("current") or ""
    return bool(current) and current not in images
