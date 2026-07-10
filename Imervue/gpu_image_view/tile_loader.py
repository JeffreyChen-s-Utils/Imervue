"""Thumbnail-wall async loading for :class:`GPUImageView`.

Spawns per-thumbnail decode workers with distance-aware priority, collects
their results into the tile cache under the grid mutex, and coalesces the
status-bar progress updates. Extracted so the view keeps thin forwarders
for the signal callbacks and the public ``load_tile_grid_async`` /
``add_thumbnail`` entry points.
"""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMutexLocker, QObject, QRunnable, QThreadPool, QTimer, Signal

from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker
from Imervue.image.browser_state import is_missing_file_error, is_transient_load_error

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# Low-frequency file-existence sweep — keeps every stat call off the GL paint
# path. 4 s notices an unplugged drive promptly without hammering network
# shares the way a per-frame check would.
OFFLINE_SWEEP_INTERVAL_MS = 4000


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

    _spawn_thumbnail_workers(view, image_paths, gen)
    start_offline_sweep(view)

    if hasattr(view.main_window, "show_progress"):
        view.main_window.show_progress(0, view._tile_load_total)
    # 同步 list view（若處於 list 模式或之後會切換）
    if hasattr(view.main_window, "refresh_list_view"):
        with contextlib.suppress(Exception):
            view.main_window.refresh_list_view()
    view.update()


def _spawn_thumbnail_workers(view: GPUImageView, image_paths, gen: int) -> None:
    from Imervue.gpu_image_view.worker_pools import priority_for_distance
    model_positions = {path: i for i, path in enumerate(getattr(view.model, "images", []))}
    hover_path = getattr(view, "_hover_tile_path", None)
    ordered = sorted(
        image_paths,
        key=lambda p: (
            0 if p == hover_path else 1,
            abs(model_positions.get(p, 0) - getattr(view, "focused_tile_index", 0)),
        ),
    )
    for path in ordered:
        worker = LoadThumbnailWorker(path, view.thumbnail_size, gen)
        worker.signals.finished.connect(view._on_thumbnail_loaded)
        if hasattr(worker.signals, "error"):
            worker.signals.error.connect(view._on_thumbnail_error)
        track_tile_worker(view, worker)
        # Tiles near the current selection get higher priority so a fresh
        # folder-open shows the user's viewport first even if the pool can't
        # drain the full list before they start scrolling.
        distance = abs(model_positions.get(path, 0) - getattr(view, "focused_tile_index", 0))
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


def on_thumbnail_loaded(view: GPUImageView, img_data, path, generation) -> None:
    """Worker callback: stash one decoded thumbnail and schedule a refresh."""
    if generation != view._load_generation:
        return
    if path not in view.model.images:
        return
    with QMutexLocker(view.grid_mutex):
        view.tile_cache[path] = img_data
    getattr(view, "tile_errors", {}).pop(path, None)
    getattr(view, "_tile_error_toasted", set()).discard(path)
    getattr(view, "offline_paths", set()).discard(path)
    getattr(view, "_tile_retry_counts", {}).pop(path, None)
    if hasattr(view.main_window, "clear_image_issue"):
        view.main_window.clear_image_issue(path)
    view._tile_load_times[path] = time.monotonic()
    sig = _file_signature(path)
    if sig is not None:
        signatures = getattr(view, "_tile_file_signatures", None)
        if not isinstance(signatures, dict):
            signatures = {}
            view._tile_file_signatures = signatures
        signatures[path] = sig
    view._overlay.ensure_fade_pump()

    # Coalesce the progress update — a folder of N thumbnails finishing in
    # quick succession otherwise re-lays out the status bar N times. The
    # coalescer caps that at one update per ~16 ms; the force-flush makes
    # sure the bar lands at 100 % even if the last tile arrived inside the
    # window.
    _bump_tile_progress(view)
    view.update()


def on_thumbnail_error(view: GPUImageView, path: str, message: str, generation: int) -> None:
    """Worker callback: record a visible per-tile load failure."""
    if generation != view._load_generation:
        return
    if path not in view.model.images:
        return
    message = message or "Load failed"
    if is_missing_file_error(message):
        _record_missing_tile(view, path, message)
    else:
        _record_failed_tile(view, path, message, generation)
    view._filmstrip_pending.discard(path)
    _bump_tile_progress(view)
    view.update()


def _record_missing_tile(view: GPUImageView, path: str, message: str) -> None:
    """A vanished file renders as a quiet 'Missing' slot, not a red failure."""
    getattr(view, "offline_paths", set()).add(path)
    getattr(view, "tile_errors", {}).pop(path, None)
    if hasattr(view.main_window, "record_image_issue"):
        view.main_window.record_image_issue(path, message)


def _record_failed_tile(view: GPUImageView, path: str, message: str, generation: int) -> None:
    getattr(view, "tile_errors", {})[path] = message
    if hasattr(view.main_window, "record_image_issue"):
        view.main_window.record_image_issue(path, message)
    _maybe_retry_thumbnail(view, path, message, generation)
    toasted = getattr(view, "_tile_error_toasted", set())
    if path not in toasted and hasattr(view.main_window, "toast"):
        toasted.add(path)
        lang = view.main_window.language_wrapper.language_word_dict
        view.main_window.toast.error(
            lang.get("tile_load_failed_named", "Couldn't load thumbnail: {name}").format(
                name=Path(path).name,
            ),
        )


def _completed_tile_count(view: GPUImageView) -> int:
    """Tiles in a terminal state — decoded, failed, or missing on disk."""
    done = set(view.tile_cache)
    done.update(getattr(view, "tile_errors", {}))
    done.update(getattr(view, "offline_paths", set()).intersection(view.model.images))
    return len(done)


def _bump_tile_progress(view: GPUImageView) -> None:
    view._tile_load_count = _completed_tile_count(view)
    view._progress_coalescer.schedule()
    if view._tile_load_count >= getattr(view, "_tile_load_total", 0):
        view._progress_coalescer.force_flush()


def _maybe_retry_thumbnail(view: GPUImageView, path: str, message: str, generation: int) -> None:
    if not is_transient_load_error(message):
        return
    retry_counts = getattr(view, "_tile_retry_counts", None)
    if not isinstance(retry_counts, dict):
        retry_counts = {}
        view._tile_retry_counts = retry_counts
    count = retry_counts.get(path, 0)
    if count >= 2:
        return
    retry_counts[path] = count + 1
    QTimer.singleShot(
        200 * (count + 1),
        lambda p=path, gen=generation: _retry_thumbnail(view, p, gen),
    )


def _retry_thumbnail(view: GPUImageView, path: str, generation: int) -> None:
    if generation != getattr(view, "_load_generation", None):
        return
    if path not in getattr(getattr(view, "model", None), "images", []):
        return
    getattr(view, "tile_errors", {}).pop(path, None)
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
    if hasattr(worker.signals, "error"):
        worker.signals.error.connect(view._on_thumbnail_error)
    track_tile_worker(view, worker)
    view.thumbnail_pool.start(worker)


def on_filmstrip_thumbnail_loaded(view: GPUImageView, img_data, path,
                                  generation) -> None:
    """Worker callback: clear the in-flight marker then stash the thumbnail."""
    view._filmstrip_pending.discard(path)
    add_thumbnail(view, img_data, path, generation)


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
    _spawn_thumbnail_workers(view, missing, gen)
    start_offline_sweep(view)
    if hasattr(view.main_window, "refresh_list_view"):
        with contextlib.suppress(Exception):
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
    tex = view.tile_textures.pop(path, None)
    if tex is not None:
        from OpenGL.GL import glDeleteTextures
        with contextlib.suppress(Exception):
            glDeleteTextures([tex])
        view._vram_usage -= view._tile_tex_sizes.pop(path, 0)


def _file_signature(path: str) -> tuple[int, int, str] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns, Path(path).suffix.lower())


class _OfflineScanSignals(QObject):
    finished = Signal(object, int)  # missing-path set, load generation


class OfflineScanWorker(QRunnable):
    """Stat every folder path off the GUI thread and report the missing set."""

    def __init__(self, paths: list[str], generation: int) -> None:
        super().__init__()
        self._paths = paths
        self._generation = generation
        self.signals = _OfflineScanSignals()

    def run(self) -> None:
        self.signals.finished.emit(scan_missing_paths(self._paths), self._generation)


def scan_missing_paths(paths) -> set[str]:
    """Pure sweep body: the subset of *paths* that no longer exist on disk."""
    return {path for path in paths if not os.path.exists(path)}


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
    worker = OfflineScanWorker(paths, view._load_generation)
    worker.signals.finished.connect(view._on_offline_scan_finished)
    QThreadPool.globalInstance().start(worker)


def on_offline_scan_finished(view: GPUImageView, missing, generation: int) -> None:
    """Apply one sweep result: flip offline states and reload recovered tiles."""
    view._offline_scan_inflight = False
    if generation != view._load_generation:
        return
    current = set(view.model.images)
    missing = set(missing) & current
    offline = getattr(view, "offline_paths", set())
    recovered = (offline & current) - missing
    newly_missing = missing - offline
    if not recovered and not newly_missing:
        return
    offline.difference_update(recovered)
    offline.update(newly_missing)
    _report_offline_changes(view, newly_missing, recovered, generation)
    view.update()


def _report_offline_changes(view: GPUImageView, newly_missing: set[str],
                            recovered: set[str], generation: int) -> None:
    record_issue = getattr(view.main_window, "record_image_issue", None)
    clear_issue = getattr(view.main_window, "clear_image_issue", None)
    if record_issue is not None:
        for path in newly_missing:
            record_issue(path, "File not found")
    for path in recovered:
        if clear_issue is not None:
            clear_issue(path)
        # The tile was drawn as "Missing" while offline — reload it now that
        # the file is back (drive re-mounted, file restored).
        if path not in view.tile_cache:
            _retry_thumbnail(view, path, generation)


def _detect_renamed_cached_paths(view: GPUImageView, old_images, new_images) -> dict[str, str]:
    signatures = getattr(view, "_tile_file_signatures", {})
    if not isinstance(signatures, dict):
        return {}
    old_only = [p for p in old_images if p not in new_images]
    new_only = [p for p in new_images if p not in old_images]
    by_sig: dict[tuple[int, int, str], list[str]] = {}
    for old in old_only:
        sig = signatures.get(old) or _file_signature(old)
        if sig is not None:
            by_sig.setdefault(sig, []).append(old)
    out: dict[str, str] = {}
    used: set[str] = set()
    for new in new_only:
        sig = _file_signature(new)
        candidates = [p for p in by_sig.get(sig, []) if p not in used]
        if not candidates:
            continue
        old = candidates[0]
        used.add(old)
        out[old] = new
    return out
