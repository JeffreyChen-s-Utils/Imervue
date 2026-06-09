"""Deep-zoom neighbour prefetch scheduling for :class:`GPUImageView`.

This controller owns the prefetch state (cache, in-flight workers, the
navigation-direction tracker) and the orchestration logic that decides
which neighbours to load, cancels stale workers, and evicts stale cache
entries. The Qt view delegates to it but keeps thin ``@property`` shims
(``_prefetch_cache`` / ``_prefetch_workers`` / ``_cancel_all_prefetch``)
so external callers — the main window's debug HUD and the overlay
painter — keep reading the same attributes they always have.

The pure policy (which indices, which direction) lives in
:mod:`Imervue.gpu_image_view.images.prefetch`; this module is the
stateful glue that wires that policy to the worker pool and the cache.
"""

from __future__ import annotations

import contextlib
from collections import OrderedDict
from typing import TYPE_CHECKING

from PySide6.QtCore import QMutex, QMutexLocker

from Imervue.gpu_image_view.images.image_loader import LoadDeepZoomWorker
from Imervue.gpu_image_view.images.prefetch import (
    NavigationDirectionTracker,
    compute_prefetch_targets,
    range_for_direction,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# Deep-zoom prefetch window (±N images) and the resulting cache ceiling.
PREFETCH_RANGE = 3
PREFETCH_MAX = PREFETCH_RANGE * 2 + 1

# Fallback distance for a path no longer in the model — keeps the worker
# at the back of the priority queue until the next cancel pass drops it.
_MISSING_DISTANCE = 99


class PrefetchScheduler:
    """Own and orchestrate the deep-zoom neighbour prefetch."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view
        self._mutex = QMutex()
        self.cache: OrderedDict[str, object] = OrderedDict()  # path -> DeepZoomImage
        self.workers: dict[str, LoadDeepZoomWorker] = {}  # path -> worker
        self._nav_tracker = NavigationDirectionTracker()

    # -- scheduling --------------------------------------------------

    def schedule(self) -> None:
        """Load the current image's ±N neighbours into the cache."""
        images = self._view.model.images
        if not images:
            return
        needed = self._compute_targets(images)
        with QMutexLocker(self._mutex):
            self._cancel_outdated_workers(needed)
            self._evict_outdated_cache(needed)
            self._spawn_workers(needed)

    def _compute_targets(self, images: list[str]) -> set[str]:
        """Return the set of paths to prefetch around ``current_index``.

        The window is asymmetric when the user has been navigating in
        one direction — biased ahead on forward paging, behind on
        backward — so the cache budget lands on images the user is
        actually about to view. Falls back to symmetric ±PREFETCH_RANGE
        when navigation looks scattered (jump-around browsing).
        """
        current = self._view.current_index
        self._nav_tracker.record(current)
        range_ahead, range_behind = range_for_direction(self._nav_tracker.direction())
        indices = compute_prefetch_targets(
            current, len(images),
            range_ahead=range_ahead, range_behind=range_behind,
        )
        return {images[i] for i in indices}

    def _cancel_outdated_workers(self, needed: set[str]) -> None:
        # list() required: we mutate self.workers in-loop.
        for path in list(self.workers):  # noqa: S7504
            if path not in needed:
                self.workers.pop(path).abort()

    def _evict_outdated_cache(self, needed: set[str]) -> None:
        # list() required: we del from self.cache in-loop.
        for path in list(self.cache):  # noqa: S7504
            if path not in needed:
                del self.cache[path]

    def _distance_for(self, path: str) -> int:
        """Return |index(path) - current_index| for the priority helper.

        Defaults to a large distance when the path isn't in the model —
        happens during transient races; the queue will drop the worker
        on the next ``_cancel_outdated`` pass.
        """
        try:
            return abs(self._view.model.images.index(path) - self._view.current_index)
        except (ValueError, AttributeError):
            return _MISSING_DISTANCE

    def _spawn_workers(self, needed: set[str]) -> None:
        from Imervue.gpu_image_view.worker_pools import priority_for_distance
        from Imervue.image.recipe_store import recipe_store
        for path in needed:
            if path in self.cache or path in self.workers:
                continue
            worker = LoadDeepZoomWorker(path, recipe=recipe_store.get_for_path(path))
            worker.signals.finished.connect(self._view._on_prefetch_loaded)
            self.workers[path] = worker
            # Distance-aware priority: the next neighbour the user might
            # press lands before the far-out ones, so when the pool
            # drains it pulls the most-likely-needed image first
            # regardless of submit order.
            distance = self._distance_for(path)
            self._view.prefetch_pool.start(worker, priority_for_distance(distance))

    # -- worker completion -------------------------------------------

    def pop_worker(self, path: str) -> None:
        """Drop the finished worker for ``path`` under the lock."""
        with QMutexLocker(self._mutex):
            self.workers.pop(path, None)

    def store(self, path: str, dzi: object) -> None:
        """Cache a freshly prefetched image, trimming to PREFETCH_MAX."""
        with QMutexLocker(self._mutex):
            self.cache[path] = dzi
            while len(self.cache) > PREFETCH_MAX:
                self.cache.popitem(last=False)

    # -- cache access / teardown -------------------------------------

    def take(self, path: str) -> object | None:
        """Pop and return a cached image, or None on miss."""
        return self.cache.pop(path, None)

    def has(self, path: str) -> bool:
        return path in self.cache

    def has_worker(self, path: str) -> bool:
        return path in self.workers

    def discard(self, path: str) -> None:
        """Drop a single cached image (e.g. after a recipe edit)."""
        with contextlib.suppress(KeyError):
            del self.cache[path]

    def cancel_all(self) -> None:
        """Cancel all in-flight workers, clear the cache, reset direction."""
        for worker in self.workers.values():
            with contextlib.suppress(RuntimeError, TypeError):
                worker.signals.finished.disconnect()
            worker.abort()
        self.workers.clear()
        self.cache.clear()
        # Folder change → forget the previous folder's navigation history
        # so the new folder starts with a symmetric window.
        self._nav_tracker.reset()
