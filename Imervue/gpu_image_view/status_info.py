"""Status-bar synchronisation for :class:`GPUImageView`.

Builds the index / resolution / size / zoom / cursor / colour-label fields
for the main-window status bar from the view's current state. Pure glue —
extracted so the view keeps a thin ``_update_status_info`` forwarder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _format_file_size(path: str) -> str:
    """Return a human-readable size for ``path``, or "" if unavailable."""
    import os
    try:
        size_bytes = os.path.getsize(path)
    except OSError:
        return ""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def update_status_info(view: GPUImageView) -> None:
    """Push current image / zoom / cursor info to the main-window status bar."""
    mw = view.main_window
    if not hasattr(mw, "update_status_info"):
        return
    images = view.model.images
    idx = view.current_index

    if not view.deep_zoom or not images or idx >= len(images):
        _update_no_image(view, mw, images, idx)
        return

    path = images[idx]
    base = view.deep_zoom.levels[0]
    h, w = base.shape[:2]

    from Imervue.user_settings.color_labels import get_color_label
    mw.update_status_info(
        index=f"{idx + 1}/{len(images)}",
        resolution=f"{w}×{h}",
        size=_format_file_size(path),
        zoom=f"{view.zoom * 100:.0f}%",
        cursor=_format_cursor(view, w, h),
        label=get_color_label(path) or "",
    )


def _update_no_image(view: GPUImageView, mw, images: list[str], idx: int) -> None:
    """Status-bar update path for tile-grid / unloaded-image states."""
    if not images:
        mw.clear_status_info()
        return
    index_text = (
        f"{idx + 1}/{len(images)}" if view.deep_zoom
        else f"— / {len(images)}"
    )
    mw.update_status_info(
        index=index_text,
        resolution="", size="", zoom="", cursor="",
    )


def _format_cursor(view: GPUImageView, w: int, h: int) -> str:
    if view._hover_image_xy is None:
        return ""
    cx, cy = view._hover_image_xy
    if 0 <= cx < w and 0 <= cy < h:
        return f"x={cx}, y={cy}"
    return ""
