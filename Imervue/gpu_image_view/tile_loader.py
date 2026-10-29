"""Thumbnail-wall async loading for :class:`GPUImageView`.

Spawns per-thumbnail decode workers with distance-aware priority and owns the
worker slots, the retry and filmstrip spawns and the offline-sweep timer. The
result handling, the image-list sync and the file sweep live in the
``tile_loader_results`` / ``tile_loader_sync`` / ``tile_loader_offline``
siblings; this module stays the public import location for all of them, so the
view keeps thin forwarders for the signal callbacks and the public
``load_tile_grid_async`` / ``add_thumbnail`` entry points.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThreadPool

from Imervue.system.best_effort import best_effort
from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker
from Imervue.gpu_image_view.tile_viewport import viewport_for
from Imervue.gpu_image_view.thumbnail_queue import ThumbnailQueue
from Imervue.gpu_image_view.tile_loader_offline import (
    OfflineScanWorker,
    file_signature,
    on_offline_scan_finished,
    refetch_list_rows,
    refresh_rewritten_tile,
    scan_folder_paths,
)
from Imervue.gpu_image_view.tile_loader_results import (
    _bump_tile_progress,
    add_thumbnail,
    image_is_current,
    on_filmstrip_thumbnail_loaded,
    on_thumbnail_error,
    on_thumbnail_loaded,
)
from Imervue.gpu_image_view.tile_loader_sync import (
    images_changed,
    needs_filmstrip_thumbnail,
    reset_view_memory_on_switch,
    sync_tile_grid_incremental,
    tile_grid_needs_reload,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

__all__ = [
    "OFFLINE_SWEEP_INTERVAL_MS",
    "OfflineScanWorker",
    "add_thumbnail",
    "discard_tile_worker",
    "ensure_filmstrip_thumbnail",
    "file_signature",
    "flush_thumbnail_progress",
    "image_is_current",
    "images_changed",
    "load_tile_grid_async",
    "needs_filmstrip_thumbnail",
    "on_filmstrip_thumbnail_loaded",
    "on_offline_scan_finished",
    "on_thumbnail_error",
    "on_thumbnail_loaded",
    "pump_thumbnail_workers",
    "refetch_list_rows",
    "refresh_rewritten_tile",
    "reset_view_memory_on_switch",
    "scan_folder_paths",
    "start_offline_sweep",
    "stop_offline_sweep",
    "sync_tile_grid_incremental",
    "tick_offline_sweep",
    "tile_grid_needs_reload",
    "track_tile_worker",
]

# Low-frequency file sweep — keeps every stat call off the GL paint path. 4 s
# notices an unplugged drive, or a picture another program rewrote, promptly
# without hammering network shares the way a per-frame check would.
OFFLINE_SWEEP_INTERVAL_MS = 4000


def load_tile_grid_async(view: GPUImageView, image_paths) -> None:
    """Reset the wall and start bounded viewport-first thumbnail decoding."""
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
    view._tile_max_dimensions = (0, 0)
    getattr(view, "tile_errors", {}).clear()
    getattr(view, "_tile_error_toasted", set()).clear()
    getattr(view, "offline_paths", set()).clear()
    getattr(view, "_tile_retry_counts", {}).clear()
    view._filmstrip_pending.clear()
    view._delete_all_tile_textures()
    view._clear_deep_zoom()

    view.tile_grid_mode = True
    view._tile_load_total = len(image_paths)
    view._tile_load_count = 0

    _spawn_thumbnail_workers(view, gen)
    start_offline_sweep(view)

    if hasattr(view.main_window, "show_progress"):
        view.main_window.show_progress(0, view._tile_load_total)
    # 同步 list view（若處於 list 模式或之後會切換）
    if hasattr(view.main_window, "refresh_list_view"):
        with best_effort("refresh the list view"):
            view.main_window.refresh_list_view()
    view.update()


def _spawn_thumbnail_workers(view: GPUImageView, gen: int) -> None:
    limit = getattr(view.thumbnail_pool, "maxThreadCount", lambda: 8)()
    view._tile_queue = ThumbnailQueue(view.model.images, gen, limit=limit)
    pump_thumbnail_workers(view)


def pump_thumbnail_workers(view: GPUImageView) -> None:
    """Admit viewport or explicit jobs only when a real worker slot is free."""
    queue = getattr(view, "_tile_queue", None)
    if queue is None or queue.generation != view._load_generation:
        return
    queue.sync(view.model.images)
    paths = queue.plan(
        viewport_for(view), view.tile_cache, getattr(view, "tile_errors", {}),
        getattr(view, "offline_paths", set()), wall=getattr(view, "tile_grid_mode", True),
        hover=getattr(view, "_hover_tile_path", None),
        full_resolution=view.thumbnail_size is None,
    )
    slots = max(0, queue.limit - len(view.active_tile_workers))
    for path in paths[:slots]:
        if not image_is_current(view, path):
            queue.urgent.pop(path, None)
            queue.requested.discard(path)
            continue
        worker = LoadThumbnailWorker(path, view.thumbnail_size, queue.generation)
        mode = queue.started(path, worker)
        callback = (view._on_filmstrip_thumbnail_loaded if mode == "filmstrip"
                    else view._on_thumbnail_loaded)
        worker.signals.finished.connect(callback)
        if hasattr(worker.signals, "error"):
            worker.signals.error.connect(view._on_thumbnail_error)
        track_tile_worker(view, worker)
        view.thumbnail_pool.start(worker, 10)
    view._tile_load_total = len(queue.requested)
    _bump_tile_progress(view)


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
    error_signal = getattr(worker.signals, "error", None)
    if error_signal is not None:
        error_signal.connect(lambda *_args, _w=worker: discard_tile_worker(view, _w))


def discard_tile_worker(view: GPUImageView, worker) -> None:
    """Drop a finished/aborted *worker* from the in-flight set (idempotent).

    Keyed on worker identity, so a late eviction landing after a folder switch
    already rebuilt the set is a harmless no-op rather than a cross-generation
    corruption.
    """
    view.active_tile_workers.discard(worker)
    queue = getattr(view, "_tile_queue", None)
    if queue is not None and queue.active.get(worker.path) is worker:
        queue.active.pop(worker.path)
        pump_thumbnail_workers(view)


def _retry_thumbnail(
    view: GPUImageView, path: str, generation: int, *, replay: bool = False,
) -> None:
    if generation != getattr(view, "_load_generation", None):
        return
    if not image_is_current(view, path):
        return
    getattr(view, "tile_errors", {}).pop(path, None)
    queue = getattr(view, "_tile_queue", None)
    if queue is not None:
        queue.request(path, replay=replay)
        pump_thumbnail_workers(view)
        return
    worker = LoadThumbnailWorker(path, view.thumbnail_size, generation)
    worker.signals.finished.connect(view._on_thumbnail_loaded)
    if hasattr(worker.signals, "error"):
        worker.signals.error.connect(view._on_thumbnail_error)
    track_tile_worker(view, worker)
    view.thumbnail_pool.start(worker)


def flush_thumbnail_progress(view: GPUImageView) -> None:
    """Coalesced status-bar update — forwards the latest counter."""
    if hasattr(view.main_window, "show_progress"):
        view.main_window.show_progress(view._tile_load_count, view._tile_load_total)


def ensure_filmstrip_thumbnail(view: GPUImageView, path: str) -> None:
    """Schedule one deduplicated thumbnail decode for a cold filmstrip path.

    The wall warms its visible buffer; filmstrip paths outside it, direct file
    opens and folder refreshes may still be cold. A managed queue admits these
    explicit requests within its worker slots and shares an existing decode.
    Legacy direct-open views retain one worker per missing path. Results land
    through generation checks so a folder change cannot insert stale pixels.
    """
    if (not path or path in view.tile_cache or path in view._filmstrip_pending
            or not image_is_current(view, path)):
        return
    view._filmstrip_pending.add(path)
    queue = getattr(view, "_tile_queue", None)
    if queue is not None:
        queue.request(path, filmstrip=True)
        pump_thumbnail_workers(view)
        return
    worker = LoadThumbnailWorker(path, view.thumbnail_size, view._load_generation)
    worker.signals.finished.connect(view._on_filmstrip_thumbnail_loaded)
    if hasattr(worker.signals, "error"):
        worker.signals.error.connect(view._on_thumbnail_error)
    track_tile_worker(view, worker)
    view.thumbnail_pool.start(worker)


def start_offline_sweep(view: GPUImageView) -> None:
    """Run an immediate existence scan, then keep it repeating on the timer.

    No-op on views without the sweep timer (stub views in tests), so the
    loaders stay callable with plain fakes.
    """
    timer = getattr(view, "_offline_sweep_timer", None)
    if timer is None:
        return
    tick_offline_sweep(view)
    timer.start()


def stop_offline_sweep(view: GPUImageView) -> None:
    timer = getattr(view, "_offline_sweep_timer", None)
    if timer is not None:
        timer.stop()


def tick_offline_sweep(view: GPUImageView) -> None:
    """Spawn one background stat sweep unless one is already in flight."""
    if getattr(view, "_offline_scan_inflight", False):
        return
    if not getattr(view, "tile_grid_mode", False):
        return
    paths = list(view.model.images)
    if not paths:
        return
    view._offline_scan_inflight = True
    known = dict(getattr(view, "_tile_file_signatures", {}))   # a snapshot for the worker thread
    worker = OfflineScanWorker(paths, view._load_generation, known)
    worker.signals.finished.connect(view._on_offline_scan_finished)
    QThreadPool.globalInstance().start(worker)
