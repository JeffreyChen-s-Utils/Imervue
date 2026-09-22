"""Neighbour prefetch and memory pressure of the viewer.

Decodes the images next to the current one ahead of time, and when the
process's resident memory passes its limit drops the prefetch cache and the
tile textures before the OS starts swapping. ``GPUImageView`` mixes these
methods in.
"""
from __future__ import annotations

import contextlib


from Imervue.image.tile_manager import TileManager


class PrefetchMemoryMixin:
    """Neighbour prefetch and memory pressure of the viewer."""

    @property
    def _prefetch_cache(self):
        """Prefetch cache (path → DeepZoomImage). Read by the main-window
        debug HUD and the overlay painter — external contract, keep stable."""
        return self._prefetch.cache

    @property
    def _prefetch_workers(self):
        """In-flight prefetch workers (path → worker). Read by the overlay
        painter's debug HUD — external contract, keep stable."""
        return self._prefetch.workers

    def _prefetch_neighbors(self):
        """載入當前圖片前後 ±N 張到記憶體快取"""
        self._prefetch.schedule()

    def _on_prefetch_loaded(self, dzi, path):
        """預載 worker 完成回調"""
        self._prefetch.pop_worker(path)

        # 如果使用者正在等待這張圖（prefetch worker 被當作主載入用）
        from Imervue.gpu_image_view.view_state import resolve_loaded_index
        idx = resolve_loaded_index(self.model.images, self.current_index, path)
        if (self.deep_zoom is None
                and self._deep_zoom_loading == path
                and idx is not None):
            self.current_index = idx
            self.deep_zoom = dzi
            self.tile_manager = TileManager(dzi)
            self._finalize_deep_zoom_display(path)
            return

        # 否則存入預載快取
        self._prefetch.store(path, dzi)

    def _on_prefetch_error(self, path: str, message: str) -> None:
        """A prefetch worker failed. Drop it, and — if the user is waiting on it
        as the primary load (``load_deep_zoom_image`` delegated to an already
        in-flight prefetch worker) — route to the normal failure handling.

        Without this the prefetch error only popped the worker, leaving
        ``_deep_zoom_loading`` set and ``deep_zoom`` None: a permanent "Loading…"
        overlay with no error toast and no retry.
        """
        self._prefetch.pop_worker(path)
        if self.deep_zoom is None and self._deep_zoom_loading == path:
            self._on_deep_zoom_failed(path, message, self._deep_zoom_request_id)

    def enforce_memory_pressure(self) -> None:
        """Trim deep-zoom auxiliary caches when image memory is large."""
        base = self.deep_zoom.levels[0] if self.deep_zoom is not None else None
        if base is None:
            return
        base_bytes = int(base.nbytes)
        ram_bytes = self._process_rss_bytes()
        if base_bytes > self._vram_limit * 0.35:
            self._cancel_all_prefetch()
        if base_bytes > self._vram_limit * 0.20:
            self._filmstrip_thumb_cache.clear()
            self._filmstrip_pending.clear()
        manager = self.tile_manager
        cache = getattr(manager, "cache", None)
        if cache is not None and base_bytes > self._vram_limit * 0.50:
            manager.max_cache = 64
            from OpenGL.GL import glDeleteTextures
            # Trim runs from the display path, off paintGL — free in-context.
            with self._current_gl_context():
                while len(cache) > 64:
                    _, tex = cache.popitem(last=False)
                    with contextlib.suppress(Exception):
                        glDeleteTextures([tex])
        elif manager is not None:
            manager.max_cache = 256
        if ram_bytes and ram_bytes > self._ram_pressure_limit_bytes():
            self._cancel_all_prefetch()
            self._filmstrip_thumb_cache.clear()
            self._filmstrip_pending.clear()
            self.tile_cache.clear()
            if manager is not None:
                manager.max_cache = min(getattr(manager, "max_cache", 256), 48)

    @staticmethod
    def _process_rss_bytes() -> int:
        with contextlib.suppress(Exception):
            import psutil
            return int(psutil.Process().memory_info().rss)
        return 0

    @staticmethod
    def _ram_pressure_limit_bytes() -> int:
        with contextlib.suppress(Exception):
            import psutil
            total = int(psutil.virtual_memory().total)
            return max(768 * 1024 * 1024, int(total * 0.70))
        return 2 * 1024 * 1024 * 1024
