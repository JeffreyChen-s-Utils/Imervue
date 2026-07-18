"""Per-image zoom/pan memory and random-image jump for :class:`GPUImageView`.

``save`` / ``restore`` remember each image's zoom + offsets so paging back
to a previously-viewed image returns to where the user left it.
``jump_to_random`` powers the X-key "show me a random photo" shortcut.
``resolve_loaded_index`` maps a just-finished deep-zoom load back to its model
row so list churn during the load can't strand the image.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_DEFAULT_ZOOM = 1.0


def resolve_loaded_index(images: list[str], current_index: int,
                         path: str) -> int | None:
    """Model row to display a just-finished deep-zoom *path* at, or ``None``.

    The completion handlers already established *path* is the wanted load (the
    request id and ``_deep_zoom_loading`` both matched); this only maps it back
    to a row. The async folder scan re-sorting, a filter change, or a
    watch-folder refresh can reorder ``model.images`` between the click and the
    load finishing, so ``current_index`` may no longer point at *path*. Prefer
    that index when it still does (no lookup); otherwise re-locate *path* rather
    than dropping the finished image on the tile wall — the "clicking an image
    doesn't enter deep zoom" report. Return ``None`` only when *path* has
    genuinely left the folder, the one case where discarding the load is right.
    """
    if not images:
        return None
    if 0 <= current_index < len(images) and images[current_index] == path:
        return current_index
    try:
        return images.index(path)
    except ValueError:
        return None


def _current_base_dims(view: GPUImageView) -> tuple[int, int] | None:
    """Base-level ``(w, h)`` of the image currently in deep zoom, else None.

    Saved alongside the zoom so a later reload can tell whether the image's
    geometry changed (rotate/crop) and the remembered zoom is stale.
    """
    dz = getattr(view, "deep_zoom", None)
    if dz is None:
        return None
    base = dz.levels[0]
    return (base.shape[1], base.shape[0])


def save_view_state(view: GPUImageView) -> None:
    """Remember the currently-displayed image's zoom + pan.

    Keyed on ``_deep_zoom_path`` — the image whose view ``view.zoom`` /
    offsets actually reflect — NOT ``images[current_index]``. Navigation
    advances ``current_index`` to the *incoming* image before the load runs,
    so keying on it would save the outgoing image's zoom under the incoming
    image's slot: the incoming entry gets corrupted and the outgoing image's
    own view is lost. When no image is on screen there is nothing to save.
    """
    path = getattr(view, "_deep_zoom_path", None)
    if not path:
        return
    view._view_memory[path] = {
        "zoom": view.zoom,
        "dx": view.dz_offset_x,
        "dy": view.dz_offset_y,
        "dims": _current_base_dims(view),
        # Whether this was a deliberate user zoom/pan (True) or a whole-image
        # fit (False). A remembered *fit* must re-fit to the canvas on reload —
        # a fit saved on a larger screen otherwise reads as a zoom-in on a
        # smaller one and opens cropped. Only a genuine zoom-in is preserved.
        "locked": bool(getattr(view, "_user_locked_view", False)),
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
