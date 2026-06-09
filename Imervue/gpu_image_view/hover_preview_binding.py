"""Tile-wall hover-preview popup binding for :class:`GPUImageView`.

Detects which thumbnail sits under the cursor and arms / disarms the
shared hover-preview popup. Extracted so the view keeps thin forwarders;
the popup widget itself lives in :mod:`Imervue.gui.hover_preview`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def ensure_controller(view: GPUImageView):
    """Lazily create the popup controller (avoids import without QApplication)."""
    if view._hover_controller is None:
        from Imervue.gui.hover_preview import HoverPreviewController
        view._hover_controller = HoverPreviewController()
    return view._hover_controller


def update_hover_preview(view: GPUImageView, event) -> None:
    """Detect which tile (if any) sits under the cursor and arm the popup."""
    # Skip while the user is actively dragging or selecting — the popup would
    # get in the way of the drag-select rectangle.
    if view._drag_selecting or view._middle_dragging or view._drag_start_pos:
        cancel_hover_preview(view)
        return

    mx, my = event.position().x(), event.position().y()
    hovered_path = _tile_under_cursor(view, mx, my)
    if hovered_path is None:
        cancel_hover_preview(view)
        return

    if hovered_path != view._hover_last_path:
        view._hover_last_path = hovered_path
        ctrl = ensure_controller(view)
        ctrl.arm(hovered_path, event.globalPosition().toPoint())


def _tile_under_cursor(view: GPUImageView, mx: float, my: float) -> str | None:
    for x0, y0, x1, y1, path in view.tile_rects:
        if x0 <= mx <= x1 and y0 <= my <= y1:
            return path
    return None


def cancel_hover_preview(view: GPUImageView) -> None:
    """Disarm the popup and forget the last-hovered path."""
    view._hover_last_path = None
    if view._hover_controller is not None:
        view._hover_controller.disarm()
