"""Thumbnail-wall image-list changes: incremental sync and refill policies.

Updates the wall in place when the folder's list changes (keeping warm
thumbnails, migrating renamed files, carrying focus and selection over), and
holds the pure policies that decide a folder switch or a cold-cache refill.
Split from :mod:`tile_loader`, which re-exports the public names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.system.best_effort import best_effort
from Imervue.gpu_image_view.tile_loader_offline import file_signature

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def tile_grid_needs_reload(tile_cache, images) -> bool:
    """Whether an unmanaged legacy cache needs an initial wall load.

    A live viewport queue bypasses this fallback and refills only missing
    candidates, keeping its warm cache and saved offsets on Escape. Direct
    file/recent/bookmark paths without a queue still need initial scheduling.
    """
    if not images:
        return False
    return any(image not in tile_cache for image in images)


def images_changed(current_images, new_image_paths) -> bool:
    """Whether ``load_tile_grid_async`` is switching to a different image set.

    A genuine folder switch replaces the list; a same-folder reload (thumbnail
    size change, cold-cache refill, grid-mode session restore) passes the
    identical paths. Only the former should reset per-folder view state. Pure so
    the policy is unit-testable without a Qt widget.
    """
    return list(current_images) != list(new_image_paths)


def reset_view_memory_on_switch(view: GPUImageView, new_image_paths) -> bool:
    """Drop per-folder deep-zoom view memory + lock on a genuine folder switch.

    ``_view_memory`` (per-image zoom/pan) and ``_user_locked_view`` (whether the
    user has taken manual zoom/pan control) are scoped to the current folder's
    browsing session. Carrying them across a folder switch strands the next
    deep-zoom open with the previous folder's zoom — the resize/show fit nets
    stay suppressed by the stale lock and the save-before-restore path seeds the
    new image with the old zoom — so it opens without fitting to the window.
    Clearing them makes every image in the new folder a fresh fit.

    Returns ``True`` when a reset happened (list changed); a same-folder reload
    keeps the remembered zoom/pan and returns ``False``.
    """
    if not images_changed(view.model.images, new_image_paths):
        return False
    view._view_memory.clear()
    view._user_locked_view = False
    return True


def needs_filmstrip_thumbnail(path, tile_cache, pending, images) -> bool:
    """Whether *path* needs a lazy thumbnail decode for the filmstrip/preview.

    The filmstrip and the deep-zoom loading preview both read their pixmaps from
    ``tile_cache``. Skip a request when the path is falsy, already cached,
    already in flight, or no longer in the live image list (a stale paint after
    the folder changed). Pure so the dedup policy is unit-testable.
    """
    if not path or path in tile_cache or path in pending:
        return False
    return path in images


def sync_tile_grid_incremental(view: GPUImageView, image_paths: list[str]) -> None:
    """Update the thumbnail wall without dropping warm cache or scroll state."""
    image_paths = list(image_paths)
    old_images = list(view.model.images)
    if old_images == image_paths:
        return

    rename_map = _detect_renamed_cached_paths(view, old_images, image_paths)
    if rename_map:
        from Imervue.image.browser_state import migrate_view_path_state
        migrate_view_path_state(view, rename_map)
        signatures = getattr(view, "_tile_file_signatures", {})
        for old, new in rename_map.items():
            if old in signatures and new not in signatures:
                signatures[new] = signatures.pop(old)

    view._cancel_tile_workers()
    view._load_generation += 1
    gen = view._load_generation

    new_set = set(image_paths)
    for path in [p for p in old_images if p not in new_set]:
        _drop_tile_path(view, path)

    old_focus_path = (
        old_images[view.focused_tile_index]
        if 0 <= getattr(view, "focused_tile_index", -1) < len(old_images)
        else None
    )
    view.model.set_images(image_paths)
    view.selected_tiles.intersection_update(new_set)

    if old_focus_path in new_set:
        view.focused_tile_index = image_paths.index(old_focus_path)
    elif image_paths:
        view.focused_tile_index = min(max(getattr(view, "focused_tile_index", 0), 0),
                                      len(image_paths) - 1)
    else:
        from Imervue.gpu_image_view.tile_focus import NO_FOCUS
        view.focused_tile_index = NO_FOCUS

    missing = [
        path for path in image_paths
        if path not in view.tile_cache and path not in getattr(view, "tile_errors", {})
    ]
    view.tile_grid_mode = True
    view._tile_load_total = len(missing)
    view._tile_load_count = 0
    # Worker spawning lives in tile_loader, which imports this module.
    from Imervue.gpu_image_view.tile_loader import _spawn_thumbnail_workers, start_offline_sweep
    _spawn_thumbnail_workers(view, gen)
    start_offline_sweep(view)
    if hasattr(view.main_window, "refresh_list_view"):
        with best_effort("refresh the list view"):
            view.main_window.refresh_list_view()
    view.update()


def _drop_tile_path(view: GPUImageView, path: str) -> None:
    view.tile_cache.pop(path, None)
    getattr(view, "tile_errors", {}).pop(path, None)
    getattr(view, "_tile_error_toasted", set()).discard(path)
    getattr(view, "offline_paths", set()).discard(path)
    view._filmstrip_thumb_cache.pop(path, None)
    view._filmstrip_pending.discard(path)
    view._tile_load_times.pop(path, None)
    getattr(view, "_tile_file_signatures", {}).pop(path, None)
    # Free under the widget's GL context and keep the VRAM accounting in sync —
    # a bare glDeleteTextures here (off paintGL) is silently dropped and leaks.
    from Imervue.gpu_image_view.tile_textures import free_tile_textures
    free_tile_textures(view, (path,))


def _detect_renamed_cached_paths(view: GPUImageView, old_images, new_images) -> dict[str, str]:
    signatures = getattr(view, "_tile_file_signatures", {})
    if not isinstance(signatures, dict):
        return {}
    old_only = [p for p in old_images if p not in new_images]
    new_only = [p for p in new_images if p not in old_images]
    by_sig: dict[tuple[int, int, str], list[str]] = {}
    for old in old_only:
        sig = signatures.get(old) or file_signature(old)
        if sig is not None:
            by_sig.setdefault(sig, []).append(old)
    out: dict[str, str] = {}
    used: set[str] = set()
    for new in new_only:
        sig = file_signature(new)
        candidates = [p for p in by_sig.get(sig, []) if p not in used]
        if not candidates:
            continue
        old = candidates[0]
        used.add(old)
        out[old] = new
    return out
