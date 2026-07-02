"""Thumbnail-wall async loading for :class:`GPUImageView`.

Spawns per-thumbnail decode workers with distance-aware priority, collects
their results into the tile cache under the grid mutex, and coalesces the
status-bar progress updates. Extracted so the view keeps thin forwarders
for the signal callbacks and the public ``load_tile_grid_async`` /
``add_thumbnail`` entry points.
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QMutexLocker

from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def load_tile_grid_async(view: GPUImageView, image_paths) -> None:
    """Reset the wall and queue a thumbnail-decode worker per image."""
    view._cancel_tile_workers()
    view._cancel_deep_zoom_worker()
    view._cancel_all_prefetch()
    view._load_generation += 1
    gen = view._load_generation

    # Compared against the *old* list before set_images below, so a genuine
    # folder switch drops the previous folder's per-image zoom memory and view
    # lock — otherwise the next deep-zoom open inherits stale state and skips
    # its auto-fit-to-window.
    reset_view_memory_on_switch(view, image_paths)
    view.model.set_images(image_paths)
    view.tile_cache.clear()
    view._filmstrip_pending.clear()
    view._delete_all_tile_textures()
    view._clear_deep_zoom()

    view.tile_grid_mode = True
    view._tile_load_total = len(image_paths)
    view._tile_load_count = 0

    _spawn_thumbnail_workers(view, image_paths, gen)

    if hasattr(view.main_window, "show_progress"):
        view.main_window.show_progress(0, view._tile_load_total)
    # 同步 list view（若處於 list 模式或之後會切換）
    if hasattr(view.main_window, "refresh_list_view"):
        with contextlib.suppress(Exception):
            view.main_window.refresh_list_view()
    view.update()


def _spawn_thumbnail_workers(view: GPUImageView, image_paths, gen: int) -> None:
    from Imervue.gpu_image_view.worker_pools import priority_for_distance
    for index, path in enumerate(image_paths):
        worker = LoadThumbnailWorker(path, view.thumbnail_size, gen)
        worker.signals.finished.connect(view._on_thumbnail_loaded)
        track_tile_worker(view, worker)
        # Tiles near the current selection get higher priority so a fresh
        # folder-open shows the user's viewport first even if the pool can't
        # drain the full list before they start scrolling.
        distance = abs(index - view.current_index)
        view.thumbnail_pool.start(worker, priority_for_distance(distance))


def track_tile_worker(view: GPUImageView, worker) -> None:
    """Register *worker* for cancellation and wire it to self-evict on finish.

    ``QThreadPool`` auto-deletes each runnable once ``run()`` returns, but the
    Python wrapper — and its ``WorkerSignals`` ``QObject`` — lingers in
    ``active_tile_workers`` until the next folder switch clears the whole set.
    Over a long browse of a large folder, plus one worker per filmstrip lazy
    load, that retains a dead worker per thumbnail and makes
    ``_cancel_tile_workers`` churn O(n) disconnect/abort calls over workers that
    already finished. Evicting on completion keeps the set bounded to genuinely
    in-flight workers.
    """
    view.active_tile_workers.add(worker)
    worker.signals.finished.connect(
        lambda *_args, _w=worker: discard_tile_worker(view, _w)
    )


def discard_tile_worker(view: GPUImageView, worker) -> None:
    """Drop a finished/aborted *worker* from the in-flight set (idempotent).

    Keyed on worker identity, so a late eviction landing after a folder switch
    already rebuilt the set is a harmless no-op rather than a cross-generation
    corruption.
    """
    view.active_tile_workers.discard(worker)


def on_thumbnail_loaded(view: GPUImageView, img_data, path, generation) -> None:
    """Worker callback: stash one decoded thumbnail and schedule a refresh."""
    if generation != view._load_generation:
        return
    if path not in view.model.images:
        return
    with QMutexLocker(view.grid_mutex):
        view.tile_cache[path] = img_data
    view._tile_load_times[path] = time.monotonic()
    view._overlay.ensure_fade_pump()

    view._tile_load_count = len(view.tile_cache)
    # Coalesce the progress update — a folder of N thumbnails finishing in
    # quick succession otherwise re-lays out the status bar N times. The
    # coalescer caps that at one update per ~16 ms; the force-flush makes
    # sure the bar lands at 100 % even if the last tile arrived inside the
    # window.
    view._progress_coalescer.schedule()
    if view._tile_load_count >= view._tile_load_total:
        view._progress_coalescer.force_flush()
    view.update()


def flush_thumbnail_progress(view: GPUImageView) -> None:
    """Coalesced status-bar update — forwards the latest counter."""
    if hasattr(view.main_window, "show_progress"):
        view.main_window.show_progress(view._tile_load_count, view._tile_load_total)


def add_thumbnail(view: GPUImageView, img_data, path, generation=None) -> None:
    """Insert a thumbnail directly (undo_delete restore path)."""
    if generation is not None and generation != view._load_generation:
        return
    if path not in view.model.images:
        return
    view.tile_cache[path] = img_data
    view._tile_load_times[path] = time.monotonic()
    view._overlay.ensure_fade_pump()
    view.update()


def tile_grid_needs_reload(tile_cache, images) -> bool:
    """Whether entering tile-grid mode must reload the wall instead of reusing
    the cache.

    The thumbnail wall renders straight from ``tile_cache`` and has no per-tile
    lazy refill — a tile missing from the cache stays a blank placeholder until
    the whole wall is reloaded. Paths that reach grid mode over a cold or only
    partially-warmed cache must therefore trigger a reload: pressing Esc out of
    a deep zoom that was opened through a cache-clearing route (file-tree file
    click, recent image, bookmark jump, drag-drop), restoring a grid-mode
    session, or toggling back from the list view.

    Returns ``False`` for an empty folder (a blank wall is the correct result)
    and when every image already has a cached thumbnail (the warm common case),
    so the warm path keeps its scroll/zoom state and never flickers. Pure so the
    policy is unit-testable without a Qt widget.
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


def ensure_filmstrip_thumbnail(view: GPUImageView, path: str) -> None:
    """Schedule one deduplicated thumbnail decode for a cold filmstrip path.

    Normally the tile-wall loader fills ``tile_cache`` for the whole folder, but
    paths that enter deep zoom without a wall pass — opening a file directly, or
    a folder auto-refresh while zoomed — leave it cold, so the filmstrip and the
    low-res loading preview render blank. This fills the gap on demand: at most
    one worker per missing path, landing through the generation-checked
    ``add_thumbnail`` so a folder change in flight can't insert a stale tile.
    """
    if not needs_filmstrip_thumbnail(
        path, view.tile_cache, view._filmstrip_pending, view.model.images,
    ):
        return
    view._filmstrip_pending.add(path)
    worker = LoadThumbnailWorker(path, view.thumbnail_size, view._load_generation)
    worker.signals.finished.connect(view._on_filmstrip_thumbnail_loaded)
    track_tile_worker(view, worker)
    view.thumbnail_pool.start(worker)


def on_filmstrip_thumbnail_loaded(view: GPUImageView, img_data, path,
                                  generation) -> None:
    """Worker callback: clear the in-flight marker then stash the thumbnail."""
    view._filmstrip_pending.discard(path)
    add_thumbnail(view, img_data, path, generation)
