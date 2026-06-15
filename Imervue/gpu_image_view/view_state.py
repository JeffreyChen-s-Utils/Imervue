"""Per-image zoom/pan memory and random-image jump for :class:`GPUImageView`.

``save`` / ``restore`` remember each image's zoom + offsets so paging back
to a previously-viewed image returns to where the user left it.
``jump_to_random`` powers the X-key "show me a random photo" shortcut.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_DEFAULT_ZOOM = 1.0


def save_view_state(view: GPUImageView) -> None:
    """儲存當前圖片的縮放與位置。"""
    images = view.model.images
    if images and 0 <= view.current_index < len(images):
        path = images[view.current_index]
        view._view_memory[path] = {
            "zoom": view.zoom,
            "dx": view.dz_offset_x,
            "dy": view.dz_offset_y,
        }


def restore_view_state(view: GPUImageView, path: str) -> None:
    """恢復上次的縮放與位置（無記錄則重置）。"""
    mem = view._view_memory.get(path)
    if mem:
        view.zoom = mem["zoom"]
        view.dz_offset_x = mem["dx"]
        view.dz_offset_y = mem["dy"]
    else:
        view.zoom = _DEFAULT_ZOOM
        view.dz_offset_x = 0
        view.dz_offset_y = 0


def jump_to_random(view: GPUImageView) -> None:
    """Jump to a random image, avoiding a re-pick of the current one.

    Uses ``random.choice`` deliberately — this is a UI navigation feature
    (the X-key "show me a random photo"), not a security-sensitive operation.
    There is no token / nonce / cryptographic context here, so an
    unpredictable PRNG is unnecessary and would only add overhead.
    """
    import random  # nosec B311  # NOSONAR S2245 UI navigation, not security-sensitive
    images = view.model.images
    if not images:
        return
    if len(images) == 1:
        view.current_index = 0
        view.load_deep_zoom_image(images[0])
        return
    choices = [i for i in range(len(images)) if i != view.current_index]
    idx = random.choice(choices)  # nosec B311  # NOSONAR S2245 UI navigation
    view.current_index = idx
    view.tile_grid_mode = False
    view.load_deep_zoom_image(images[idx])
