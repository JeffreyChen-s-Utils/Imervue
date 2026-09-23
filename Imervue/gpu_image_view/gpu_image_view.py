from __future__ import annotations

import logging
from typing import TYPE_CHECKING


from Imervue.system.best_effort import best_effort
from Imervue.gpu_image_view.tile_focus import NO_FOCUS
from Imervue.gpu_image_view.tile_layout import plan_tile_size_change
from Imervue.gpu_image_view.view_state_init import (
    init_browse_state,
    init_deep_zoom_state,
    init_display_state,
    init_grid_state,
    init_interaction_state,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

import os
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_MODELVIEW,
    GL_PROJECTION,
    GL_TEXTURE_2D,
    glClear,
    glClearColor,
    glDeleteTextures,
    glEnable,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glViewport,
)
from PySide6.QtCore import QThreadPool, QMutex
from PySide6.QtGui import QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from Imervue.gpu_image_view.gl_renderer import GLRenderer
import contextlib
from Imervue.gpu_image_view.deep_zoom_loading import DeepZoomLoadingMixin
from Imervue.gpu_image_view.view_fitting import ViewFittingMixin
from Imervue.gpu_image_view.prefetch_memory import PrefetchMemoryMixin
from Imervue.gpu_image_view.view_mouse import ViewMouseMixin

logger = logging.getLogger("Imervue.gpu_image_view")


class GPUImageView(
        ViewMouseMixin, PrefetchMemoryMixin, ViewFittingMixin, DeepZoomLoadingMixin,
        QOpenGLWidget):
    """OpenGL image viewer: the thumbnail tile grid and the deep-zoom single-image view."""

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__()

        self.main_window = main_window

        init_grid_state(self)
        init_deep_zoom_state(self)
        init_browse_state(self)
        init_interaction_state(self)
        self._init_workers()
        self._init_collaborators()
        init_display_state(self)

    def _init_workers(self) -> None:
        """Worker pools, progress coalescing and in-flight tile workers."""
        # ===== Thread =====
        # Per-workload pools instead of a single oversubscribed
        # global pool — see ``worker_pools.worker_pool_sizes`` for
        # the policy. Each pool runs at most its documented ceiling
        # so a folder-open burst of N thumbnail decodes can't queue
        # behind the user's current deep-zoom or the ±N prefetch.
        from Imervue.gpu_image_view.worker_pools import worker_pool_sizes
        sizes = worker_pool_sizes(os.cpu_count() or 4)
        self.thumbnail_pool = QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(sizes["thumbnail"])
        self.deepzoom_pool = QThreadPool(self)
        self.deepzoom_pool.setMaxThreadCount(sizes["deepzoom"])
        self.prefetch_pool = QThreadPool(self)
        self.prefetch_pool.setMaxThreadCount(sizes["prefetch"])
        # Legacy alias — many call sites and the Ctrl+F3 HUD still
        # reference ``self.thread_pool``. Pointing it at the
        # deep-zoom pool gives them the most-relevant counts; the
        # split pools land on their own start sites below.
        self.thread_pool = self.deepzoom_pool

        # Coalesce per-thumbnail progress + status updates into
        # one GUI-thread refresh per ~16 ms. See ``signal_coalescer``.
        from Imervue.gpu_image_view.signal_coalescer import SignalCoalescer
        self._progress_coalescer = SignalCoalescer(parent=self)
        self._progress_coalescer.flush_requested.connect(
            self._flush_thumbnail_progress,
        )
        self.grid_mutex = QMutex()  # 保護 tile_cache 併發讀寫
        self._load_generation = 0  # 世代計數器，用來取消過期的 tile worker
        # True while a folder scan is running and the wall has no images yet;
        # drives the centred "loading" spinner so a slow scan isn't a blank view.
        self._folder_scan_active = False
        # In-flight tile/filmstrip workers — a set so each self-evicts on finish
        # in O(1) instead of lingering until the next folder switch clears it.
        self.active_tile_workers = set()  # 用來追蹤/取消 Tile Grid 載入 worker
        self.active_deep_zoom_worker = None  # 當前 DeepZoom 背景 worker
        self.active_deep_zoom_preview_worker = None

    def _init_collaborators(self) -> None:
        """View-state memory, prefetch, GL renderer and the drawing / input collaborators."""
        # ===== 記憶位置 & 縮放 =====
        self._view_memory: dict[str, dict] = {}  # path → {zoom, dx, dy}

        # ===== Prefetch（DeepZoom 預載入）=====
        # The scheduler owns the cache, in-flight workers, and the
        # navigation-direction tracker; the view exposes thin shims
        # (_prefetch_cache / _prefetch_workers / _cancel_all_prefetch)
        # for external readers (main-window HUD, overlay painter).
        from Imervue.gpu_image_view.prefetch_scheduler import PrefetchScheduler
        self._prefetch = PrefetchScheduler(self)

        # ===== GL Renderer =====
        self.renderer = GLRenderer()

        # ===== Tile-wall / deep-zoom drawing collaborators =====
        from Imervue.gpu_image_view.tile_grid_renderer import TileGridRenderer
        from Imervue.gpu_image_view.deep_zoom_renderer import DeepZoomRenderer
        self._tile_renderer = TileGridRenderer(self)
        self._deep_zoom_renderer = DeepZoomRenderer(self)

        # ===== Pointer / wheel / gesture interaction =====
        from Imervue.gpu_image_view.input_controller import InputController
        self._input = InputController(self)

        # ===== QPainter overlay (OSD / HUD / histogram / badges) =====
        from Imervue.gpu_image_view.overlay_painter import OverlayPainter
        self._overlay = OverlayPainter(self)

        # ===== Keyboard-action dispatch =====
        from Imervue.gpu_image_view.key_action_dispatcher import KeyActionDispatcher
        self._key_dispatch = KeyActionDispatcher(self)

        # ===== Keyboard event routing =====
        from Imervue.gpu_image_view.key_input_handler import KeyInputHandler
        self._key_input = KeyInputHandler(self)

        # ===== Browse features (filmstrip / reading mode / pan clamp / fade) =====
        from Imervue.gpu_image_view.browse_features import BrowseFeatures
        self._browse = BrowseFeatures(self)

    # ===========================
    # Modify panel (non-destructive editing)
    # ===========================

    @property
    def _develop_panel(self):
        """Access the modify panel from the main window (may be None in tests)."""
        return getattr(self.main_window, "modify_panel", None)

    def open_develop_panel(self):
        """Switch to the Modify tab in the main QTabWidget and bind."""
        panel = self._develop_panel
        if panel is None:
            return
        images = self.model.images
        path = None
        if images and 0 <= self.current_index < len(images):
            path = images[self.current_index]
        panel.bind_to_path(path)
        # Switch to the Modify tab (index 1) in the main QTabWidget.
        main_tabs = getattr(self.main_window, "_main_tabs", None)
        if main_tabs is not None and main_tabs.count() > 1:
            main_tabs.setCurrentIndex(1)

    def _on_recipe_committed(self, path, old_recipe, new_recipe):
        """Panel committed a new recipe — push undo command + reload."""
        from Imervue.gpu_image_view.actions.recipe_commands import EditRecipeCommand
        cmd = EditRecipeCommand(self, path, old_recipe, new_recipe)
        self.undo_manager.push(cmd)

    def set_cvd_view_mode(self, mode: str | None) -> None:
        """Toggle the colour-vision-deficiency view mode and reload
        the current image so the change is immediately visible.

        The entire prefetch cache is dropped — every cached frame
        was rendered against the *previous* CVD mode and would
        flash the wrong colours when the user pages through it."""
        from Imervue.gpu_image_view.cvd_view_mode import set_view_mode
        set_view_mode(mode)
        # Burn the prefetch cache + cancel inflight workers; the
        # next paint reloads against the new mode.
        self._cancel_all_prefetch()
        self.reload_current_image_with_recipe()

    def reload_current_image_with_recipe(self, path: str | None = None):
        """Drop any cached baked pixels for ``path`` and reload it fresh.

        Called by EditRecipeCommand after it updates the recipe in the
        store. If ``path`` is None, reloads whatever's currently showing.
        """
        if path is None:
            images = self.model.images
            if not images or self.current_index >= len(images):
                return
            path = images[self.current_index]
        # Any prefetched baked tiles for this path are stale — drop them.
        self._prefetch.discard(path)
        # Force a fresh load — _clear_deep_zoom + load_deep_zoom_image will
        # ask recipe_store for the new recipe and apply it.
        if self.model.images and 0 <= self.current_index < len(self.model.images) \
                and self.model.images[self.current_index] == path:
            # Save the live zoom/pan first: _clear_deep_zoom nulls _deep_zoom_path,
            # so load_deep_zoom_image's own save would no-op and a tonal recipe
            # edit would snap the view back to the entry zoom.
            self._save_view_state()
            self._cancel_deep_zoom_worker()
            self._clear_deep_zoom()
            self.load_deep_zoom_image(path)
            # Re-bind the develop panel so slider labels reflect the new recipe.
            if self._develop_panel is not None and self._develop_panel.isVisible():
                self._develop_panel.bind_to_path(path)

    # ===========================
    # OpenGL 初始化
    # ===========================
    def initializeGL(self):
        glEnable(GL_TEXTURE_2D)
        glClearColor(0.1, 0.1, 0.1, 1)
        self.renderer.init()
        self._detect_vram_limit()
        self._init_tile_uploader()

    def _init_tile_uploader(self) -> None:
        """Allocate the PBO streaming uploader now that a GL context
        exists. Failure leaves ``_tile_uploader`` usable but not
        initialised, so :func:`upload_rgba_texture` transparently
        falls back to the synchronous path."""
        from Imervue.gpu_image_view.pbo_uploader import PBOTextureUploader
        self._tile_uploader = PBOTextureUploader()
        self._tile_uploader.initialise()

    def _detect_vram_limit(self) -> None:
        """Size the tile-cache VRAM budget to the GL driver's real VRAM."""
        from Imervue.gpu_image_view.vram_detect import detect_vram_limit
        detect_vram_limit(self)

    def resizeGL(self, w, h):
        # Qt 6 passes ``w`` / ``h`` in DEVICE pixels (the framebuffer
        # size). The fit math expects logical pixels, so we read them
        # from ``self.width() / height()`` to stay in one coordinate
        # space — mixing the two over-shoots ``pan_y`` by a factor of
        # ``dpr`` on HiDPI screens and pins the image to the bottom of
        # the canvas.
        log_w = max(1, int(self.width()))
        log_h = max(1, int(self.height()))
        dev_w = max(1, int(w))
        dev_h = max(1, int(h))
        glViewport(0, 0, dev_w, dev_h)
        if self.renderer.use_shaders:
            self.renderer.set_ortho(log_w, log_h)
        else:
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            glOrtho(0, log_w, log_h, 0, -1, 1)
            glMatrixMode(GL_MODELVIEW)
        self._last_resize_size = (log_w, log_h)
        # The canvas changed size — re-fit a whole-image view, or re-clamp a
        # deliberate zoom-in so it can't be stranded off the smaller viewport.
        self._adapt_view_to_canvas()

    def showEvent(self, event):
        """Return to a whole-image fit whenever the viewer comes back into view.

        Coming back — from another main tab, from the list / dual / timeline
        view, or after the window landed on a different monitor — means the
        canvas may be any size now, so the image always re-fits rather than
        keeping a zoom that suited the canvas it was left on.

        The re-fit itself is deferred: the widget's first ``resizeGL`` lands
        while the host frame is still at an intermediate size (a background
        stacked page only gets its real geometry after Qt drains the queued
        layout request), and fitting against that is exactly the "opens at the
        wrong size" bug. Only the unlock happens now — so an image that
        finishes loading before the deferred pass can still restore and keep
        its own remembered zoom-in.
        """
        super().showEvent(event)
        self._on_view_shown()

    def _on_view_shown(self) -> None:
        """Post-show half of :meth:`showEvent` — see there for the rationale."""
        if self.deep_zoom is None:
            return
        self._user_locked_view = False
        self._schedule_canvas_adapt()

    def hideEvent(self, event):
        """Invalidate the cached canvas size when the viewer is hidden.

        While the viewer sits behind another main tab it receives no
        ``resizeGL``, so a resize meanwhile would strand the fit math on a
        stale size (the "wrong size after switching tabs / folders" bug). The
        deferred ``showEvent`` fit re-runs after Qt's layout settles, so
        dropping the cache here makes that fit read the live geometry.
        """
        super().hideEvent(event)
        from Imervue.gpu_image_view.fit_view import invalidate_canvas_size
        invalidate_canvas_size(self)

    # ===========================
    # 繪製
    # ===========================
    def paintGL(self):
        # Same guard as PaintCanvas.paintGL — a queued paint event
        # can fire after the GL context has been torn down (test
        # teardown / window close), and ``glClear`` then raises
        # ``GLError(invalid operation)`` that propagates to the
        # whole event loop.
        from PySide6.QtGui import QOpenGLContext
        if QOpenGLContext.currentContext() is None:
            return
        painter = QPainter(self)
        painter.beginNativePainting()

        try:
            glClear(GL_COLOR_BUFFER_BIT)
        except Exception:   # noqa: BLE001 - GL context torn down
            painter.endNativePainting()
            return

        # Render the GL scene defensively: a renderer exception must never skip
        # endNativePainting + the QPainter overlay below, or the filmstrip / OSD
        # (drawn there) silently vanish for the whole frame.
        try:
            if self.tile_grid_mode:
                self._tile_renderer.paint()
            elif self.deep_zoom:
                self._deep_zoom_renderer.paint()
                self._deep_zoom_renderer.paint_minimap()
        except Exception:   # keep the overlay alive; log the cause
            logger.exception("Deep-zoom/tile GL render failed this frame")

        painter.endNativePainting()

        # ===== QPainter 文字/圖形覆蓋層 =====
        # Guard the overlay pass too: an exception escaping here would skip
        # painter.end(), leaking the widget QPainter and corrupting the next
        # GL frame (which silently drops the minimap as well as the overlay).
        try:
            self._paint_overlay(painter)
        except Exception:   # overlay failure must not leak the painter
            logger.exception("Overlay paint failed this frame")
        painter.end()

    # ---------------------------
    # Tile texture / VRAM management (drawing lives in TileGridRenderer)
    # ---------------------------
    def _ensure_tile_texture(self, path: str, img_data) -> bool:
        """Allocate a GPU texture for *path* — called by the tile renderer."""
        from Imervue.gpu_image_view.tile_textures import ensure_tile_texture
        return ensure_tile_texture(self, path, img_data)

    def _current_minimap_rect(self) -> tuple[int, int, int, int] | None:
        """Minimap rectangle (x, y, w, h) in widget coords, or None when no
        deep-zoom image is loaded. Shared by the renderer, the overlay
        painter, and the click handlers so the clickable area always
        matches what is drawn — external contract, keep stable."""
        return self._deep_zoom_renderer.current_minimap_rect()

    # ---------------------------
    # QPainter overlay (delegated to OverlayPainter)
    # ---------------------------
    def _paint_overlay(self, painter):
        """Composite the active QPainter overlay layers onto the canvas."""
        self._overlay.paint(painter)

    def _tick_placeholder(self) -> None:
        """Repaint while tile placeholders are still streaming in."""
        self._overlay.tick_placeholder()

    def _current_path(self) -> str | None:
        imgs = self.model.images
        if imgs and 0 <= self.current_index < len(imgs):
            return imgs[self.current_index]
        return None

    # ---------------------------
    # Filmstrip / reading-mode / pan-clamp behaviour lives in BrowseFeatures
    # (self._browse); the Qt event handlers below delegate to it.
    # ---------------------------
    def _update_status_info(self):
        """Sync the main-window status bar — called by viewer collaborators
        and external GUI panels. External contract, keep stable."""
        from Imervue.gpu_image_view.status_info import update_status_info
        update_status_info(self)

    # ---------------------------
    # Fit to Window — delegated to fit_view helpers
    # ---------------------------

    def _toggle_bookmark(self):
        """切換當前圖片的書籤狀態"""
        images = self.model.images
        if not images or self.current_index >= len(images):
            return
        path = images[self.current_index]
        from Imervue.user_settings.bookmark import is_bookmarked, add_bookmark, remove_bookmark
        lang = self.main_window.language_wrapper.language_word_dict
        if is_bookmarked(path):
            remove_bookmark(path)
            msg = lang.get("bookmark_removed", "Bookmark removed")
        else:
            add_bookmark(path)
            msg = lang.get("bookmark_added", "\u2605 Bookmarked")
        if hasattr(self.main_window, 'toast'):
            self.main_window.toast.info(msg)
        self.update()

    def _paste_image_from_clipboard(self):
        """Paste a clipboard image — called by the key-action dispatcher.
        External contract, keep the name/signature stable."""
        from Imervue.gpu_image_view.clipboard_paste import paste_image_from_clipboard
        paste_image_from_clipboard(self)

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

    # ---------------------------
    # Tile Grid 載入
    # ---------------------------
    def set_thumbnail_size(self, size) -> None:
        """Apply a new thumbnail size picked from the menu.

        While in deep zoom the grid is *not* rebuilt — that would drop the
        user back to the wall and wipe the status-bar info. The size is stored
        and the grid is regenerated lazily on the next exit to the wall.
        """
        self.thumbnail_size = None if size == "None" else size
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        user_setting_dict["thumbnail_size"] = self.thumbnail_size
        in_deep_zoom = self.deep_zoom is not None and not self.tile_grid_mode
        action = plan_tile_size_change(
            in_deep_zoom=in_deep_zoom, has_images=bool(self.model.images),
        )
        if action == "rebuild":
            self.clear_tile_grid()
            self.load_tile_grid_async(image_paths=self.model.images)
        elif action == "defer":
            self._tile_size_dirty = True
            self.update()

    def load_tile_grid_async(self, image_paths):
        """Load a folder's thumbnails — public entry point. External contract."""
        from Imervue.gpu_image_view.tile_loader import load_tile_grid_async
        load_tile_grid_async(self, image_paths)

    def _on_thumbnail_loaded(self, img_data, path, generation):
        from Imervue.gpu_image_view.tile_loader import on_thumbnail_loaded
        on_thumbnail_loaded(self, img_data, path, generation)

    def _on_thumbnail_error(self, path, message, generation):
        from Imervue.gpu_image_view.tile_loader import on_thumbnail_error
        on_thumbnail_error(self, path, message, generation)

    def _flush_thumbnail_progress(self) -> None:
        """Coalesced status-bar update — connected to the progress coalescer."""
        from Imervue.gpu_image_view.tile_loader import flush_thumbnail_progress
        flush_thumbnail_progress(self)

    def _tick_offline_sweep(self) -> None:
        """Timer tick: refresh ``offline_paths`` via a background stat sweep."""
        from Imervue.gpu_image_view.tile_loader import tick_offline_sweep
        tick_offline_sweep(self)

    def _on_offline_scan_finished(self, missing, generation) -> None:
        from Imervue.gpu_image_view.tile_loader import on_offline_scan_finished
        on_offline_scan_finished(self, missing, generation)

    # 保持向後相容（undo_delete 使用）
    def add_thumbnail(self, img_data, path, generation=None):
        """Insert a thumbnail directly — external contract (undo_delete)."""
        from Imervue.gpu_image_view.tile_loader import add_thumbnail
        add_thumbnail(self, img_data, path, generation)

    def _ensure_filmstrip_thumbnail(self, path: str) -> None:
        """Lazily decode *path* into ``tile_cache`` for the filmstrip / preview.

        Called from the overlay paint path when a needed thumbnail is missing
        so the filmstrip and deep-zoom loading preview self-heal regardless of
        how the cache went cold (open-file, folder refresh while zoomed)."""
        from Imervue.gpu_image_view.tile_loader import ensure_filmstrip_thumbnail
        ensure_filmstrip_thumbnail(self, path)

    def _on_filmstrip_thumbnail_loaded(self, img_data, path, generation) -> None:
        """Worker callback for a lazily-requested filmstrip thumbnail."""
        from Imervue.gpu_image_view.tile_loader import on_filmstrip_thumbnail_loaded
        on_filmstrip_thumbnail_loaded(self, img_data, path, generation)

    # ---------------------------
    # DeepZoom 非同步載入 + 預載
    # ---------------------------
    # ---------------------------
    # Hover preview
    # ---------------------------
    def _update_hover_preview(self, event) -> None:
        """Arm the tile hover popup — called by the input controller."""
        from Imervue.gpu_image_view.hover_preview_binding import update_hover_preview
        update_hover_preview(self, event)

    def _cancel_hover_preview(self) -> None:
        from Imervue.gpu_image_view.hover_preview_binding import cancel_hover_preview
        cancel_hover_preview(self)

    def leaveEvent(self, event):
        self._cancel_hover_preview()
        super().leaveEvent(event)

    # ---------------------------
    # 瀏覽歷史 (Alt+←/→) — delegated to HistoryController
    # ---------------------------
    def _push_history(self, path: str) -> None:
        """Record ``path`` in the browsing history (no-op while navigating)."""
        self._history.push(path)

    def history_back(self) -> bool:
        """Jump to the previous image. External contract (key dispatcher)."""
        return self._history.back()

    def history_forward(self) -> bool:
        """Jump to the next image. External contract (key dispatcher)."""
        return self._history.forward()

    # ---------------------------
    # 顏色標籤 (F1-F5)
    # ---------------------------
    def _apply_color_label(self, color: str) -> None:
        """Toggle ``color`` on the currently-active target(s)."""
        from Imervue.gpu_image_view.cull_actions import apply_color_label
        apply_color_label(self, color)

    def _apply_cull_state(self, state: str) -> None:
        """Apply a cull state — called by the key-action dispatcher.
        External contract, keep the name/signature stable."""
        from Imervue.gpu_image_view.cull_actions import apply_cull_state
        apply_cull_state(self, state)

    def jump_to_random_image(self) -> None:
        """Jump to a random image — external contract (key dispatcher)."""
        from Imervue.gpu_image_view.view_state import jump_to_random
        jump_to_random(self)

    def _save_view_state(self):
        from Imervue.gpu_image_view.view_state import save_view_state
        save_view_state(self)

    def _restore_view_state(self, path: str):
        from Imervue.gpu_image_view.view_state import restore_view_state
        restore_view_state(self, path)

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
    # Prefetch（預載入前後 N 張）— delegated to PrefetchScheduler
    # ---------------------------

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

    def _clamp_grid_scroll(self) -> None:
        """Hold the thumbnail-wall scroll within its content so the wheel /
        middle-drag can't flick the grid into empty space above the first row
        or below the last. Recomputes the live layout (cols / cell depend on
        the widget width, thumbnail size and DPR) so the bound always matches
        what the renderer draws this frame."""
        from Imervue.gpu_image_view.tile_layout import (
            clamp_grid_offset,
            tile_grid_layout,
        )
        base_tile = self._tile_renderer.base_size()
        draw_scale, cell, cols = tile_grid_layout(
            self.width(), base_tile, self.tile_scale,
            self.tile_padding, self.devicePixelRatio(),
        )
        self.grid_offset_y = clamp_grid_offset(
            self.grid_offset_y, len(self.model.images), cols, cell,
            base_tile * draw_scale, self.height(),
        )

    # ===========================
    # Event
    # ===========================

    def keyPressEvent(self, event):
        self._key_input.handle(event)

    def _toast(self, key: str, fallback: str) -> None:
        """Show a localized toast via the main window, if available."""
        if hasattr(self.main_window, 'toast'):
            lang = self.main_window.language_wrapper.language_word_dict
            self.main_window.toast.info(lang.get(key, fallback))

    # ===========================
    # Touchpad / Touch gestures
    # ===========================
    def event(self, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.Type.Gesture:
            self._input.handle_gesture_event(ev)
            return True
        return super().event(ev)

    # ===========================
    # Drag & Drop
    # ===========================
    def _accept_url_drag(self, event) -> None:
        """Shared handler for both dragEnterEvent and dragMoveEvent."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragEnterEvent(self, event):
        self._accept_url_drag(event)

    def dragMoveEvent(self, event):
        self._accept_url_drag(event)

    def dropEvent(self, event):
        from Imervue.gpu_image_view.drop_handler import handle_drop
        handle_drop(self, event)
