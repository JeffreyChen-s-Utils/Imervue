"""GPU, worker and animation teardown of the viewer.

Mixed into :class:`GPUImageView`: freeing tile-wall and deep-zoom
textures, cancelling tile / deep-zoom / prefetch workers, starting and
stopping animation playback, and clearing the tile wall.
"""
from __future__ import annotations

import contextlib
import logging

from OpenGL.GL import glDeleteTextures

from Imervue.gpu_image_view.tile_focus import NO_FOCUS
from Imervue.system.best_effort import best_effort

logger = logging.getLogger("Imervue.gpu_image_view")


class ViewResourcesMixin:
    """Resource teardown for :class:`GPUImageView`."""

    # Set up by view_state_init.init_deep_zoom_state; declared on the class so
    # the deep-zoom teardown's read-then-clear is visibly of a known attribute.
    _minimap_tex: int | None = None
    _minimap_dzi = None

    # ===========================
    # 載入管理
    # ===========================
    def _evict_tile_textures_if_needed(self):
        """Evict off-screen tile textures over the VRAM cap (tile renderer)."""
        from Imervue.gpu_image_view.tile_textures import evict_if_needed
        evict_if_needed(self)

    def _delete_all_tile_textures(self):
        """Free all tile-wall textures — external contract (main window)."""
        from Imervue.gpu_image_view.tile_textures import delete_all_tile_textures
        delete_all_tile_textures(self)

    def _current_gl_context(self):
        """Current this widget's GL context for texture frees issued outside
        ``paintGL`` (image switch / eviction from signal, key and menu handlers),
        so ``glDeleteTextures`` isn't dropped and the texture leaked."""
        from Imervue.gpu_image_view.gl_context import make_current_guard
        return make_current_guard(self)

    def _clear_deep_zoom(self):
        """釋放 DeepZoom 相關的 GPU 與記憶體資源"""
        self._deep_zoom_loading = None
        self._deep_zoom_path = None
        self._stop_animation()
        # Texture frees need a current GL context — this runs off paintGL.
        with self._current_gl_context():
            if self.tile_manager is not None:
                self.tile_manager.clear()
                self.tile_manager = None
            if self._minimap_tex is not None:
                glDeleteTextures([self._minimap_tex])
                self._minimap_tex = None
                self._minimap_dzi = None
        self.deep_zoom = None
        # 離開 deep zoom → 收起「修改」選單（若主視窗還在）。
        self._set_modify_menu_visible(False)
        # 清除 status bar 狀態槽 — 避免殘留上一張圖的資訊
        self._hover_image_xy = None
        if hasattr(self.main_window, "clear_status_info"):
            with best_effort("clear the status bar info", logger):
                self.main_window.clear_status_info()

    def _set_modify_menu_visible(self, visible: bool) -> None:
        """Toggle the Deep-Zoom-only Modify menu on the main window's menubar.

        Guarded against stub main windows used in tests and against the case
        where menu construction has not completed yet.
        """
        action = getattr(self.main_window, "_modify_menu_action", None)
        if action is None:
            return
        with best_effort("toggle the Modify menu", logger):
            action.setVisible(bool(visible))

    # ---------------------------
    # Worker 取消
    # ---------------------------
    def _cancel_tile_workers(self):
        self._tile_queue = None
        getattr(self, "_filmstrip_pending", set()).clear()
        for worker in self.active_tile_workers:
            with contextlib.suppress(RuntimeError, TypeError):
                worker.signals.finished.disconnect()
            with contextlib.suppress(RuntimeError, TypeError, AttributeError):
                worker.signals.error.disconnect()
            worker.abort()
        self.active_tile_workers.clear()

    def _cancel_deep_zoom_worker(self):
        if self.active_deep_zoom_worker is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self.active_deep_zoom_worker.signals.finished.disconnect()
            with contextlib.suppress(RuntimeError, TypeError, AttributeError):
                self.active_deep_zoom_worker.signals.error.disconnect()
            self.active_deep_zoom_worker.abort()
            self.active_deep_zoom_worker = None
        if self.active_deep_zoom_preview_worker is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self.active_deep_zoom_preview_worker.signals.finished.disconnect()
            with contextlib.suppress(RuntimeError, TypeError, AttributeError):
                self.active_deep_zoom_preview_worker.signals.error.disconnect()
            self.active_deep_zoom_preview_worker.abort()
            self.active_deep_zoom_preview_worker = None

    def _cancel_all_prefetch(self):
        """取消所有預載 worker 並清空快取。

        Called directly by the main window on folder change — external
        contract, keep the name/signature stable.
        """
        self._prefetch.cancel_all()

    def _init_animation(self, path: str):
        """偵測並初始化動畫播放"""
        self._stop_animation()
        from Imervue.gpu_image_view.actions.animation_player import AnimationPlayer
        player = AnimationPlayer(self, path)
        if player.load():
            self._animation = player
            player.play()

    def _stop_animation(self):
        """停止並清理動畫"""
        if self._animation is not None:
            self._animation.stop()
            self._animation = None

    # ---------------------------
    # 清除 Tile Grid
    # ---------------------------
    def clear_tile_grid(self):
        from Imervue.gpu_image_view.tile_loader import stop_offline_sweep
        stop_offline_sweep(self)
        self._cancel_tile_workers()
        self.tile_grid_mode = False
        self.tile_rects = []
        self._delete_all_tile_textures()
        self.tile_cache.clear()

        self.grid_offset_x = 0
        self.grid_offset_y = 0
        self.focused_tile_index = NO_FOCUS
        self.focus_ring_visible = False
        self._filmstrip_thumb_cache.clear()
        self._filmstrip_pending.clear()
        self._tile_load_times.clear()
        self._tile_file_signatures.clear()
        self._tile_retry_counts.clear()

        self.update()
