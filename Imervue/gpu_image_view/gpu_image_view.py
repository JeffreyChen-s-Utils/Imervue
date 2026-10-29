from __future__ import annotations

import logging
from typing import TYPE_CHECKING


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
    glEnable,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glViewport,
)
from OpenGL.error import GLError
from PySide6.QtCore import QThreadPool, QMutex
from PySide6.QtGui import QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from Imervue.gpu_image_view.gl_renderer import GLRenderer
from Imervue.gpu_image_view.deep_zoom_loading import DeepZoomLoadingMixin
from Imervue.gpu_image_view.view_fitting import ViewFittingMixin
from Imervue.gpu_image_view.prefetch_memory import PrefetchMemoryMixin
from Imervue.gpu_image_view.view_mouse import ViewMouseMixin
from Imervue.gpu_image_view.view_browse_actions import ViewBrowseActionsMixin
from Imervue.gpu_image_view.view_recipe import ViewRecipeMixin
from Imervue.gpu_image_view.view_resources import ViewResourcesMixin
from Imervue.gpu_image_view.view_tile_grid import ViewTileGridMixin

logger = logging.getLogger("Imervue.gpu_image_view")


class GPUImageView(
        ViewMouseMixin, PrefetchMemoryMixin, ViewFittingMixin, DeepZoomLoadingMixin,
        ViewRecipeMixin, ViewBrowseActionsMixin, ViewResourcesMixin, ViewTileGridMixin,
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
        except GLError:   # GL context torn down
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

    def leaveEvent(self, event):
        self._cancel_hover_preview()
        super().leaveEvent(event)

    # ===========================
    # Event
    # ===========================

    def keyPressEvent(self, event):
        self._key_input.handle(event)

    # ===========================
    # Touchpad / Touch gestures
    # ===========================
    def event(self, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.Type.Gesture:
            self._input.handle_gesture_event(ev)
            return True
        if ev.type() == QEvent.Type.KeyPress:
            from Imervue.gpu_image_view.key_input_handler import claims_tab
            if claims_tab(ev):   # QWidget spends Tab / Shift+Tab on focus before keyPressEvent
                self.keyPressEvent(ev)
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
