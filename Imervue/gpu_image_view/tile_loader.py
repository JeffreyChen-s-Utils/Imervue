"""Thumbnail-wall async loading for :class:`GPUImageView`.

Spawns per-thumbnail decode workers with distance-aware priority, collects
their results into the tile cache under the grid mutex, and coalesces the
status-bar progress updates. Extracted so the view keeps thin forwarders
for the signal callbacks and the public ``load_tile_grid_async`` /
``add_thumbnail`` entry points.
"""

from __future__ import annotations

import contextlib
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

    view.model.set_images(image_paths)
    view.tile_cache.clear()
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
        view.active_tile_workers.append(worker)
        # Tiles near the current selection get higher priority so a fresh
        # folder-open shows the user's viewport first even if the pool can't
        # drain the full list before they start scrolling.
        distance = abs(index - view.current_index)
        view.thumbnail_pool.start(worker, priority_for_distance(distance))


def on_thumbnail_loaded(view: GPUImageView, img_data, path, generation) -> None:
    """Worker callback: stash one decoded thumbnail and schedule a refresh."""
    if generation != view._load_generation:
        return
    if path not in view.model.images:
        return
    with QMutexLocker(view.grid_mutex):
        view.tile_cache[path] = img_data

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
    view.update()
