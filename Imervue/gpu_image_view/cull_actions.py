"""Colour-label and cull-state actions for :class:`GPUImageView`.

Resolves the active target(s) — multi-selected tiles, the deep-zoomed
image, the tile the arrow keys are on, or the hovered tile — and applies a
colour label or a cull state (pick / reject / unflag), surfacing a localized
toast. The rating and favourite keys resolve their targets the same way.
Extracted so the view keeps only thin forwarders for the key + menu entry
points.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.gpu_image_view.tile_focus import NO_FOCUS, focus_ring_active

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_CULL_FALLBACKS = {
    "pick": "Picked {n} image(s)",
    "reject": "Rejected {n} image(s)",
    "unflagged": "Unflagged {n} image(s)",
}


def resolve_cull_targets(view: GPUImageView) -> list[str]:
    """Resolve the image path(s) a label / cull / rating action should affect.

    Priority: multi-selected tiles → deep-zoom image → the tile the arrow
    keys are on (while its focus ring shows: moving the mouse hides it) →
    hovered tile.
    """
    if view.tile_grid_mode and view.tile_selection_mode and view.selected_tiles:
        return list(view.selected_tiles)
    if view.deep_zoom:
        images = view.model.images
        if images and 0 <= view.current_index < len(images):
            return [images[view.current_index]]
    if not view.tile_grid_mode:
        return []
    images = view.model.images
    focus = getattr(view, "focused_tile_index", NO_FOCUS)
    if focus_ring_active(getattr(view, "focus_ring_visible", False), focus, len(images)):
        return [images[focus]]
    return [view._hover_last_path] if view._hover_last_path else []


def apply_color_label(view: GPUImageView, color: str) -> None:
    """Toggle ``color`` on the currently-active target(s)."""
    from Imervue.user_settings.color_labels import set_color_label, toggle_color_label

    targets = resolve_cull_targets(view)
    if not targets:
        return

    # Single-target behaves as toggle; multi-target applies uniformly.
    if len(targets) == 1:
        new_color = toggle_color_label(targets[0], color)
        _toast_color_change(view, new_color)
    else:
        for path in targets:
            set_color_label(path, color)
        _toast_color_batch(view, color, len(targets))
    # Status bar should reflect the new label for the deep-zoomed image.
    if view.deep_zoom:
        view._update_status_info()
    view.update()


def apply_cull_state(view: GPUImageView, state: str) -> None:
    """Apply a cull ``state`` to the currently-active target(s).

    Mirrors :func:`apply_color_label` resolution order: multi-selected tiles
    → deep-zoom image → hovered tile.
    """
    from Imervue.library import image_index

    targets = resolve_cull_targets(view)
    if not targets:
        return

    for path in targets:
        image_index.set_cull_state(path, state)

    if hasattr(view.main_window, "toast"):
        lang = view.main_window.language_wrapper.language_word_dict
        fallback = _CULL_FALLBACKS[state]
        msg = lang.get(f"cull_toast_{state}", fallback).format(n=len(targets))
        view.main_window.toast.info(msg)
    if view.deep_zoom:
        view._update_status_info()
    view.update()


def _toast_color_change(view: GPUImageView, new_color: str | None) -> None:
    if not hasattr(view.main_window, "toast"):
        return
    lang = view.main_window.language_wrapper.language_word_dict
    if new_color is None:
        view.main_window.toast.info(
            lang.get("color_label_cleared", "Colour label cleared")
        )
        return
    label = lang.get(f"color_label_{new_color}", new_color.title())
    view.main_window.toast.info(
        lang.get("color_label_set", "Colour: {color}").format(color=label)
    )


def _toast_color_batch(view: GPUImageView, color: str, count: int) -> None:
    if not hasattr(view.main_window, "toast"):
        return
    lang = view.main_window.language_wrapper.language_word_dict
    label = lang.get(f"color_label_{color}", color.title())
    view.main_window.toast.info(
        lang.get("color_label_batch", "{count} images → {color}")
        .format(count=count, color=label)
    )
