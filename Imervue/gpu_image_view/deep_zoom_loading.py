"""Deep-zoom image loading of the viewer.

Opening one image: an optional low-resolution preview decode first, then the
full decode on a worker, with the stored develop recipe applied. Results that
arrive for an image the user has already left are dropped, a failed decode is
retried once, and the first displayed frame is announced so the status bar and
plugins can react. ``GPUImageView`` mixes these methods in.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer

from Imervue.gpu_image_view.images.image_loader import LoadDeepZoomWorker
from Imervue.image.browser_state import is_transient_load_error
from Imervue.image.tile_manager import TileManager


logger = logging.getLogger("Imervue.gpu_image_view")


class DeepZoomLoadingMixin:
    """Deep-zoom image loading of the viewer."""

    def load_deep_zoom_image(self, path):
        self._deep_zoom_request_id += 1
        request_id = self._deep_zoom_request_id
        self._deep_zoom_error = None
        # Whether this image was genuinely viewed before (has a remembered
        # view). ``save_view_state`` keys on the *outgoing* image, so it no
        # longer corrupts this incoming path's entry — but capture the flag
        # up front anyway as the single source of truth for the fit decision.
        self._loading_was_remembered = path in self._view_memory
        # Dims the remembered zoom was saved against, so a geometry change
        # since (rotate/crop) forces a refit instead of keeping a zoom that no
        # longer fits the swapped dimensions.
        self._loading_remembered_dims = (self._view_memory.get(path) or {}).get("dims")
        # Whether the remembered view was a deliberate zoom-in (True) or a
        # whole-image fit (False). A remembered fit re-fits to the current canvas
        # so it can't open too big / cropped after a move to a smaller screen.
        self._loading_was_locked = bool(
            (self._view_memory.get(path) or {}).get("locked", False))
        # 儲存「前一張」(目前顯示中的那張) 的狀態，key 為 _deep_zoom_path
        self._save_view_state()

        self._cancel_deep_zoom_worker()
        self._clear_deep_zoom()
        # From here on the deep-zoom target is `path`; a later save keys on it.
        self._deep_zoom_path = path

        self._push_history(path)
        self._restore_view_state(path)

        # 進入 deep zoom 模式 → 顯示「修改」選單。
        self._set_modify_menu_visible(True)

        if self.on_filename_changed:
            self.on_filename_changed(Path(path).name)

        # ===== 預載快取命中 → 立即顯示 =====
        if self._prefetch.has(path):
            dzi = self._prefetch.take(path)
            self.deep_zoom = dzi
            self.tile_manager = TileManager(dzi)
            self._finalize_deep_zoom_display(path)
            return

        # ===== 快取未命中 → 背景載入（顯示載入指示，避免空白幀）=====
        self._deep_zoom_loading = path
        if self._prefetch.has_worker(path):
            self.update()
            return

        if self._should_progressive_decode(path):
            self._start_deep_zoom_preview_worker(path, request_id)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(
                300,
                lambda p=path, req=request_id: self._start_deep_zoom_worker_if_current(p, req),
            )
        else:
            self._start_deep_zoom_worker(path, request_id)

        if hasattr(self.main_window, 'set_status'):
            self.main_window.set_status(
                self.main_window.language_wrapper.language_word_dict.get(
                    "status_loading_image", "Loading image..."
                )
            )

        self.update()

    def _start_deep_zoom_worker_if_current(self, path: str, request_id: int) -> None:
        if request_id != self._deep_zoom_request_id:
            return
        if self._deep_zoom_loading != path:
            return
        self._start_deep_zoom_worker(path, request_id)

    def _start_deep_zoom_worker(self, path: str, request_id: int) -> None:
        if self.active_deep_zoom_worker is not None:
            return
        from Imervue.image.recipe_store import recipe_store
        worker = LoadDeepZoomWorker(path, recipe=recipe_store.get_for_path(path))
        worker.signals.finished.connect(
            lambda dzi, p, req=request_id: self._on_deep_zoom_loaded(dzi, p, req)
        )
        worker.signals.error.connect(
            lambda p, msg, req=request_id: self._on_deep_zoom_failed(p, msg, req)
        )
        self.active_deep_zoom_worker = worker
        self.deepzoom_pool.start(worker)

    def _start_deep_zoom_preview_worker(self, path: str, request_id: int) -> None:
        if self.active_deep_zoom_preview_worker is not None:
            return
        from Imervue.image.recipe_store import recipe_store
        worker = LoadDeepZoomWorker(
            path,
            recipe=recipe_store.get_for_path(path),
            preview=True,
        )
        worker.signals.finished.connect(
            lambda dzi, p, req=request_id: self._on_deep_zoom_preview_loaded(dzi, p, req)
        )
        worker.signals.error.connect(lambda *_args: None)
        self.active_deep_zoom_preview_worker = worker
        self.deepzoom_pool.start(worker)

    def _should_progressive_decode(self, path: str) -> bool:
        from Imervue.gpu_image_view.images.image_loader import _RAW_EXTS
        if Path(path).suffix.lower() in _RAW_EXTS:
            return True
        try:
            # Justification: local image path picked in the browser.
            return Path(path).stat().st_size >= 60 * 1024 * 1024  # NOSONAR
        except OSError:
            return False

    def _finalize_deep_zoom_display(self, path: str) -> None:
        """Shared finalization once ``deep_zoom`` + ``tile_manager`` are set for
        *path* — reached from a prefetch cache hit, a background load, or a
        promoted in-flight prefetch worker.

        Centralised so the three display paths can't drift: a promoted prefetch
        previously skipped animation start, the second-monitor mirror, the
        status readout, and the image-issue clear purely because those calls
        were never copied into its branch.
        """
        self._deep_zoom_loading = None
        self._deep_zoom_error = None
        self._deep_zoom_retry_counts.pop(path, None)
        if hasattr(self.main_window, "clear_image_issue"):
            self.main_window.clear_image_issue(path)
        self.enforce_memory_pressure()
        self._apply_initial_view()
        self._init_animation(path)
        self._prefetch_neighbors()
        self._update_status_info()
        self._notify_deep_zoom_displayed()
        self._browse.begin_image_fade_in()
        self.update()

    def _on_deep_zoom_loaded(self, dzi, path, request_id: int | None = None):
        if request_id is not None and request_id != self._deep_zoom_request_id:
            return
        if self._deep_zoom_loading != path:
            return
        from Imervue.gpu_image_view.view_state import resolve_loaded_index
        idx = resolve_loaded_index(self.model.images, self.current_index, path)
        if idx is None:
            return
        self.current_index = idx

        if self.tile_manager is not None:
            # Off-paintGL free — needs a current GL context or it leaks.
            with self._current_gl_context():
                self.tile_manager.clear()
        self.deep_zoom = dzi
        self.tile_manager = TileManager(dzi)
        self.active_deep_zoom_worker = None
        if self.active_deep_zoom_preview_worker is not None:
            self.active_deep_zoom_preview_worker.abort()
            self.active_deep_zoom_preview_worker = None

        if hasattr(self.main_window, 'set_status'):
            self.main_window.set_status(
                self.main_window.language_wrapper.language_word_dict.get(
                    "status_ready", "Ready"
                )
            )

        # 顯示全解析度圖 → 還原記憶視圖或 fit（不受低解析度預覽的暫時 fit 影響）。
        # 共用收尾（動畫偵測、副螢幕鏡像、狀態列、預載鄰圖）。
        self._finalize_deep_zoom_display(path)

    def _on_deep_zoom_preview_loaded(self, dzi, path, request_id: int | None = None):
        if request_id is not None and request_id != self._deep_zoom_request_id:
            return
        if self._deep_zoom_loading != path:
            return
        self.active_deep_zoom_preview_worker = None
        if self.deep_zoom is None:
            self.deep_zoom = dzi
            self.tile_manager = TileManager(dzi)
            # The preview is a low-res placeholder — always fit it whole while
            # the full image loads. The final view is applied on full load via
            # ``_apply_initial_view`` (which re-restores the remembered zoom).
            self._fit_to_window()
        if hasattr(self.main_window, "set_status"):
            lang = self.main_window.language_wrapper.language_word_dict
            self.main_window.set_status(
                lang.get("status_loading_full_image", "Loading full image...")
            )
        self.update()

    def _on_deep_zoom_failed(self, path: str, message: str,
                             request_id: int | None = None) -> None:
        if request_id is not None and request_id != self._deep_zoom_request_id:
            return
        if self._deep_zoom_loading != path:
            return
        self._deep_zoom_loading = None
        # "Load failed" matches no transient-error token, so the retry check
        # below treats it exactly like an empty message.
        message = message or "Load failed"
        self._deep_zoom_error = (path, message)
        self.active_deep_zoom_worker = None
        self._maybe_retry_deep_zoom(path, message)
        if hasattr(self.main_window, "record_image_issue"):
            self.main_window.record_image_issue(path, message)
        if path not in self.model.images:
            self.offline_paths.add(path)
        if hasattr(self.main_window, "toast"):
            lang = self.main_window.language_wrapper.language_word_dict
            self.main_window.toast.error(
                lang.get("image_load_failed", "Couldn't load image: {name}").format(
                    name=Path(path).name,
                ),
            )
        if hasattr(self.main_window, "set_status"):
            self.main_window.set_status(message or "Load failed")
        self.update()

    def _maybe_retry_deep_zoom(self, path: str, message: str) -> None:
        if not is_transient_load_error(message):
            return
        count = self._deep_zoom_retry_counts.get(path, 0)
        if count >= 2:
            return
        self._deep_zoom_retry_counts[path] = count + 1
        request_id = self._deep_zoom_request_id
        QTimer.singleShot(
            250 * (count + 1),
            lambda p=path, req=request_id: self._retry_deep_zoom_if_current(p, req),
        )

    def _retry_deep_zoom_if_current(self, path: str, request_id: int) -> None:
        if request_id != self._deep_zoom_request_id:
            return
        if path not in self.model.images:
            return
        self.load_deep_zoom_image(path)

    def _notify_deep_zoom_displayed(self) -> None:
        """Push the edited base-level array to the deep-zoom-displayed hook."""
        callback = self.on_deep_zoom_displayed
        if callable(callback) and self.deep_zoom is not None:
            # pylint: disable=not-callable  # guarded by callable() above
            callback(self.deep_zoom.levels[0])
        self._log_overlay_diagnostics()

    def _log_overlay_diagnostics(self) -> None:
        """Record (at DEBUG) the inputs that decide filmstrip / minimap /
        letterbox visibility, so an 'overlays missing / image cropped' report
        can be pinned from the log without a live debugger."""
        if not logger.isEnabledFor(logging.DEBUG):
            return
        try:
            from Imervue.gpu_image_view.fit_view import (
                canvas_size,
                content_size,
                fit_zoom,
                reserved_overlay_height,
            )
            logger.debug(
                "overlay-state: images=%d filmstrip_enabled=%s grid=%s "
                "canvas=%s content=%s reserved=%d zoom=%.4f fit=%.4f off_y=%.1f",
                len(self.model.images), getattr(self, "_filmstrip_enabled", None),
                self.tile_grid_mode, canvas_size(self), content_size(self),
                reserved_overlay_height(self), self.zoom, fit_zoom(self),
                self.dz_offset_y,
            )
        except Exception:  # noqa: BLE001 - diagnostics must never break display
            logger.exception("overlay-state diagnostics failed")
