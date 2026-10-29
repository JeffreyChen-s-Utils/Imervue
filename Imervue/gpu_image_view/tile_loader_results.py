"""Thumbnail-wall worker results: landing, failure states, retries and progress.

Applies one decode worker's outcome to the view: a landed thumbnail goes into
the tile cache under the grid mutex, a failure becomes a quiet 'Missing' slot
or a toasted error with a bounded transient retry, and the status-bar counter
is coalesced. Split from :mod:`tile_loader`, which re-exports the public names.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMutexLocker

from Imervue.system.qt_timers import call_later
from Imervue.image.browser_state import is_missing_file_error, is_transient_load_error
from Imervue.gpu_image_view.tile_viewport import record_tile_extent
from Imervue.gpu_image_view.tile_loader_offline import file_signature

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def image_is_current(view: GPUImageView, path: str) -> bool:
    """Validate a worker source against the live model with indexed membership."""
    queue = getattr(view, "_tile_queue", None)
    images = getattr(getattr(view, "model", None), "images", [])
    if queue is None:
        return path in images
    return queue.contains(images, path)


def on_thumbnail_loaded(view: GPUImageView, img_data, path, generation) -> None:
    """Worker callback: stash one decoded thumbnail and schedule a refresh."""
    if generation != view._load_generation:
        return
    if not image_is_current(view, path):
        return
    _finish_filmstrip_request(view, path)
    if path in view.tile_cache and path in getattr(view, "tile_textures", {}):
        # A fresh decode of a rewritten file: the texture still holds the old pixels.
        from Imervue.gpu_image_view.tile_textures import free_tile_textures
        free_tile_textures(view, (path,))
    with QMutexLocker(view.grid_mutex):
        view.tile_cache[path] = img_data
    record_tile_extent(view, img_data)
    getattr(view, "tile_errors", {}).pop(path, None)
    getattr(view, "_tile_error_toasted", set()).discard(path)
    getattr(view, "offline_paths", set()).discard(path)
    getattr(view, "_tile_retry_counts", {}).pop(path, None)
    if hasattr(view.main_window, "clear_image_issue"):
        view.main_window.clear_image_issue(path)
    view._tile_load_times[path] = time.monotonic()
    sig = file_signature(path)
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
    if not image_is_current(view, path):
        return
    message = message or "Load failed"
    if is_missing_file_error(message):
        _record_missing_tile(view, path, message)
    else:
        _record_failed_tile(view, path, message, generation)
    _finish_filmstrip_request(view, path)
    _bump_tile_progress(view)
    view.update()


def _finish_filmstrip_request(view: GPUImageView, path: str) -> None:
    view._filmstrip_pending.discard(path)
    queue = getattr(view, "_tile_queue", None)
    if queue is not None and queue.urgent.get(path) == "filmstrip":
        queue.urgent.pop(path)


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
    queue = getattr(view, "_tile_queue", None)
    if queue is not None:
        return queue.completed_count(view.tile_cache, getattr(view, "tile_errors", {}),
                                     getattr(view, "offline_paths", set()))
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
    # Worker spawning lives in tile_loader, which imports this module.
    from Imervue.gpu_image_view.tile_loader import _retry_thumbnail
    call_later(
        200 * (count + 1), view,
        lambda p=path, gen=generation: _retry_thumbnail(view, p, gen),
    )


def add_thumbnail(view: GPUImageView, img_data, path, generation=None) -> None:
    """Insert a thumbnail directly (undo_delete restore path)."""
    if generation is not None and generation != view._load_generation:
        return
    if not image_is_current(view, path):
        return
    view.tile_cache[path] = img_data
    record_tile_extent(view, img_data)
    view._tile_load_times[path] = time.monotonic()
    view._overlay.ensure_fade_pump()
    view.update()


def on_filmstrip_thumbnail_loaded(view: GPUImageView, img_data, path,
                                  generation) -> None:
    """Worker callback: clear the in-flight marker then stash the thumbnail."""
    if generation != view._load_generation and getattr(view, "_tile_queue", None) is not None:
        return
    view._filmstrip_pending.discard(path)
    add_thumbnail(view, img_data, path, generation)
