from __future__ import annotations

import logging
from typing import TYPE_CHECKING


from Imervue.gpu_image_view.images.image_loader import LoadDeepZoomWorker
from Imervue.gpu_image_view.minimap import point_in_rect
from Imervue.gpu_image_view.tile_focus import NO_FOCUS
from Imervue.gpu_image_view.tile_layout import (
    DEFAULT_THUMBNAIL_SIZE,
    plan_tile_size_change,
    resolve_thumbnail_size,
)
from Imervue.gpu_image_view.images.image_model import ImageModel
from Imervue.menu.right_click_menu import right_click_context_menu

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
from PySide6.QtCore import QThreadPool, QMutex, Qt
from PySide6.QtGui import QUndoStack, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from pathlib import Path

from Imervue.gpu_image_view.gl_renderer import GLRenderer
from Imervue.image.tile_manager import TileManager
import contextlib

logger = logging.getLogger("Imervue.gpu_image_view")


class GPUImageView(QOpenGLWidget):
    def __init__(self, main_window: ImervueMainWindow):
        super().__init__()

        self.main_window = main_window

        # ===== Undo =====
        self.undo_stack = []  # legacy delete undo
        self.undo_manager = QUndoStack(self)

        # ===== Tile Grid =====
        self.tile_grid_mode = False
        self.selected_image_path = None
        self.tile_rects = []  # 用來存每個 tile 的 rectangle
        self.grid_offset_x = 0
        self.grid_offset_y = 0
        self.tile_scale = 1.0
        # Effective per-tile draw scale = tile_scale / devicePixelRatio,
        # recomputed each ``paint_tile_grid`` so thumbnails keep a consistent
        # physical size across monitors with different display scaling.
        self._tile_draw_scale = 1.0
        # Set when the thumbnail size changes while in deep zoom, so the grid
        # is rebuilt at the new size when the user exits back to the wall.
        self._tile_size_dirty = False
        # Keyboard focus cursor — index into ``model.images`` of the tile
        # highlighted for arrow-key navigation. NO_FOCUS (-1) means nothing is
        # focused yet, so the highlight only shows once the user starts
        # keyboard-browsing and never bothers mouse-only users.
        self.focused_tile_index = NO_FOCUS
        self.tile_textures = {}
        self.tile_cache = {}  # path -> img_data
        # path -> monotonic arrival time, for the thumbnail fade-in animation.
        self._tile_load_times: dict[str, float] = {}
        # Async PBO streaming uploader; allocated in initializeGL once a
        # GL context exists. Stays None (synchronous fallback) until then.
        self._tile_uploader = None

        # ===== DeepZoom =====
        self.zoom = 1.0
        self.dz_offset_x = 0
        self.dz_offset_y = 0
        self.last_pos = None
        self.tile_manager = None
        self.deep_zoom = None
        # Path of the image whose full pyramid is loading in the background.
        # While set (and ``deep_zoom`` is still None) the overlay shows a
        # low-res preview + "Loading…" pill instead of a blank frame.
        self._deep_zoom_loading: str | None = None
        self._saved_tile_state = None
        # True while the user is click-dragging inside the deep-zoom minimap
        # to pan the viewport.
        self._minimap_dragging = False
        # When True, the user has zoomed / panned manually so the
        # canvas should not auto-fit on resize. Cleared on every
        # fresh image load via :meth:`_fit_to_window`.
        self._user_locked_view = False
        # Snapshot (taken before the per-load save) of whether the image being
        # loaded had a genuinely remembered view, so a fresh entry always fits.
        self._loading_was_remembered = False
        # Most-recent ``resizeGL`` size — same role as the paint
        # canvas's ``_last_resize_size``. Used by ``_fit_to_window``
        # so the initial centre uses the GL-reported logical size
        # rather than ``self.width()`` / ``height()`` which can lag
        # the actual layout for the first frame or two.
        self._last_resize_size: tuple[int, int] = (0, 0)


        # ===== 圖片切換控制 =====
        self.model = ImageModel()
        self.model.images = []  # 所有圖片路徑
        self.current_index = 0
        self.on_filename_changed = None
        # Fired with the edited full-resolution base-level array once a deep-zoom
        # image is on screen. The multi-monitor mirror uses it to show the same
        # edited result the main viewer shows (not the raw file on disk).
        self.on_deep_zoom_displayed = None
        self.deep_zoom_tile_size = 512
        self._slideshow_opacity = 1.0

        # ===== 篩選前完整圖片列表 =====
        self._unfiltered_images: list[str] = []

        # ===== 縮圖排列密度 =====
        # 0 (compact) / 8 (standard) / 16 (relaxed) — 縮圖間額外 padding 像素
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        self.tile_padding = int(user_setting_dict.get("tile_padding", 8))
        # Persisted thumbnail size — survives restarts (validated against the
        # known sizes so a corrupt value can't break the grid).
        self.thumbnail_size = resolve_thumbnail_size(
            user_setting_dict.get("thumbnail_size", DEFAULT_THUMBNAIL_SIZE),
        )

        # ===== 底部縮圖膠卷（deep-zoom filmstrip）=====
        # 在單張檢視時於畫面底部顯示鄰近縮圖，點選即可跳圖。可由設定關閉。
        self._filmstrip_enabled = bool(
            user_setting_dict.get("filmstrip_enabled", True),
        )
        # path -> QPixmap，膠卷與低解析載入預覽共用；換資料夾時清空。
        self._filmstrip_thumb_cache: dict = {}

        # ===== 切換淡入轉場 =====
        # 顯示新的單張圖時讓它淡入，連續翻圖更順。可由設定關閉。
        self._transition_enabled = bool(
            user_setting_dict.get("image_transition_enabled", True),
        )
        from Imervue.gpu_image_view.view_animator import ImageFadeController
        self._image_fade = ImageFadeController(self)

        # ===== Hover 預覽 =====
        # Lazy-init 避免在沒有 QApplication 時匯入失敗
        self._hover_controller = None
        self._hover_last_path: str | None = None

        # ===== 瀏覽歷史 =====
        # 每次進入 deep zoom 的圖片會被 push 到 history controller。
        # 前進/後退移動指標，不重寫 stack（除非使用者跳到新圖則 truncate）。
        from Imervue.gpu_image_view.history_controller import HistoryController
        self._history = HistoryController(self)

        # ===== Tile Grid 選取模式 =====
        self.tile_selection_mode = False  # 是否在選取模式
        self.selected_tiles = set()  # 已選取的 tile path
        self.long_press_threshold = 500  # 長按進入選取模式的毫秒
        self._press_timer = None
        self._drag_selecting = False  # 是否正在拖曳框選
        self._drag_start_pos = None
        self._drag_end_pos = None

        # ===== Mouse =====
        self._middle_dragging = False
        self.press_pos = None

        # ===== 框選放大（deep-zoom rubber-band zoom）=====
        # 深縮放時左鍵拖一個方框 → 放大到該區域填滿畫面。
        self._zoom_band_active = False
        self._zoom_band_start = None
        self._zoom_band_end = None

        # ===== 平滑導覽：緩動縮放 + 慣性平移 =====
        # 會改變操作手感，預設關閉；user_setting 開啟後生效。
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        self._smooth_nav_enabled = bool(
            user_setting_dict.get("smooth_navigation_enabled", False),
        )
        from Imervue.gpu_image_view.view_animator import (
            PanMomentumController,
            ZoomEaseController,
        )
        self._zoom_ease = ZoomEaseController(self)
        self._pan_momentum = PanMomentumController(self)
        self._last_pan_velocity = (0.0, 0.0)

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
        self.active_tile_workers = []  # 用來追蹤/取消 Tile Grid 載入 worker
        self.active_deep_zoom_worker = None  # 當前 DeepZoom 背景 worker

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

        # ===== VRAM 管理 =====
        # 保守預設 1.5 GB。initializeGL() 會嘗試用 NVX/ATI 擴充詢問 GPU 實際 VRAM，
        # 抓到的話會覆寫成實體 VRAM 的 ~40%，在顯卡強的機器上可大幅放寬 tile cache。
        self._vram_usage = 0  # 目前 tile grid 紋理佔用 bytes
        self._vram_limit = int(1.5 * 1024 * 1024 * 1024)  # 1.5 GB fallback
        self._vram_limit_default = self._vram_limit
        self._tile_tex_sizes: dict[str, int] = {}  # path → texture bytes

        # ===== 直方圖 =====
        self._show_histogram = False
        self._histogram_cache: tuple | None = None  # (path, Histogram, ClipStats)

        # ===== OSD (On-Screen Display) =====
        # F3 — 切換右上角顯示檔名 / 尺寸 / 格式 / 檔案大小
        self._show_osd = False
        # Ctrl+F3 — Debug HUD：VRAM、tile cache、執行緒池等技術資訊
        self._show_debug_hud = False
        # 目前滑鼠在圖片上的像素座標（update_status 用，paint_pixel_view 用）
        self._hover_image_xy: tuple[int, int] | None = None
        # OSD 的 EXIF 行快取：(path, lines)，避免每幀重讀檔案
        self._exif_osd_cache: tuple | None = None
        # Shift+P — 像素檢視模式：zoom >= 4x 時顯示像素網格 + RGB 值
        self._pixel_view = False
        # L — 放大鏡 loupe：跟著游標顯示局部放大，挑片/對焦確認用
        self._loupe_enabled = False
        # Shift+滾輪 在 loupe 開啟時調整放大倍率（見 overlay_painter）。
        from Imervue.gpu_image_view.overlay_painter import LOUPE_MAGNIFICATION
        self._loupe_magnification = LOUPE_MAGNIFICATION
        # W — 閱讀模式：fit 寬度 + 垂直捲動，捲到底自動接下一張（webtoon/長圖）
        self._reading_mode = False

        # ===== 動畫播放 =====
        self._animation: object | None = None  # AnimationPlayer instance

        # ===== Minimap =====
        self._minimap_tex = None  # GL texture id
        self._minimap_dzi = None  # 對應的 DeepZoomImage，用來偵測是否需要重建

        # 原本 deep zoom 模式下 5 秒不動就會自動藏起 menu/status/tree/exif — 使用者
        # 反映會擋到檢視流程，移除此行為。保留 mouseTracking 讓 cursor 位置更新
        # 等其他仰賴 mouse move 事件的功能繼續運作。
        self.setMouseTracking(True)

        # ===== Focus ======
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        # ===== Drag & Drop =====
        self.setAcceptDrops(True)

        # ===== 觸控板手勢 =====
        # Pinch → deep zoom 縮放；Swipe 左右 → 切換圖片
        self.grabGesture(Qt.GestureType.PinchGesture)
        self.grabGesture(Qt.GestureType.SwipeGesture)

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
        # Re-fit while the user hasn't taken view control, so the
        # image stays centred when docks finish laying out and the
        # widget reaches its real size after the first resize.
        if not self._user_locked_view and self.deep_zoom is not None:
            self._fit_to_window()

    def showEvent(self, event):
        """Defer a fit-to-window until after Qt's first layout pass.

        The widget's first ``resizeGL`` lands while the host frame is
        still at an intermediate size — the fit math anchors to that
        smaller width / height and the image ends up half off-screen
        once the layout settles. ``QTimer.singleShot(0, …)`` runs
        after Qt drains its layout queue so the deferred fit catches
        the post-layout size.
        """
        super().showEvent(event)
        if self.deep_zoom is not None and not self._user_locked_view:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._fit_to_window)

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
        except Exception:   # noqa: BLE001 - keep the overlay alive; log the cause
            logger.exception("Deep-zoom/tile GL render failed this frame")

        painter.endNativePainting()

        # ===== QPainter 文字/圖形覆蓋層 =====
        self._paint_overlay(painter)
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
    def _fit_zoom(self) -> float:
        """Zoom level that fits the whole image in the canvas (capped at 1.0)."""
        from Imervue.gpu_image_view.fit_view import fit_zoom
        return fit_zoom(self)

    def _should_refit_on_load(self) -> bool:
        """Content-fit on display unless the user has a genuine zoom-in saved
        for this image (see :func:`fit_view.should_refit_on_load`)."""
        from Imervue.gpu_image_view.fit_view import should_refit_on_load
        return should_refit_on_load(self._loading_was_remembered, self)

    def _fit_to_window(self):
        """Centre + fit the image. Called by the input controller and loaders."""
        from Imervue.gpu_image_view.fit_view import fit_to_window
        fit_to_window(self)

    def _fit_to_width(self):
        """Fit image width — external contract (key dispatcher)."""
        from Imervue.gpu_image_view.fit_view import fit_to_width
        fit_to_width(self)

    def _fit_to_height(self):
        """Fit image height — external contract (key dispatcher)."""
        from Imervue.gpu_image_view.fit_view import fit_to_height
        fit_to_height(self)

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

    def _clear_deep_zoom(self):
        """釋放 DeepZoom 相關的 GPU 與記憶體資源"""
        self._deep_zoom_loading = None
        self._stop_animation()
        if self.tile_manager is not None:
            self.tile_manager.clear()
            self.tile_manager = None
        self.deep_zoom = None
        # 清除 minimap texture
        if self._minimap_tex is not None:
            glDeleteTextures([self._minimap_tex])
            self._minimap_tex = None
            self._minimap_dzi = None
        # 離開 deep zoom → 收起「修改」選單（若主視窗還在）。
        self._set_modify_menu_visible(False)
        # 清除 status bar 狀態槽 — 避免殘留上一張圖的資訊
        self._hover_image_xy = None
        if hasattr(self.main_window, "clear_status_info"):
            with contextlib.suppress(Exception):
                self.main_window.clear_status_info()

    def _set_modify_menu_visible(self, visible: bool) -> None:
        """Toggle the Deep-Zoom-only Modify menu on the main window's menubar.

        Guarded against stub main windows used in tests and against the case
        where menu construction has not completed yet.
        """
        action = getattr(self.main_window, "_modify_menu_action", None)
        if action is None:
            return
        with contextlib.suppress(Exception):
            action.setVisible(bool(visible))

    # ---------------------------
    # Worker 取消
    # ---------------------------
    def _cancel_tile_workers(self):
        for worker in self.active_tile_workers:
            with contextlib.suppress(RuntimeError, TypeError):
                worker.signals.finished.disconnect()
            worker.abort()
        self.active_tile_workers.clear()

    def _cancel_deep_zoom_worker(self):
        if self.active_deep_zoom_worker is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self.active_deep_zoom_worker.signals.finished.disconnect()
            self.active_deep_zoom_worker.abort()
            self.active_deep_zoom_worker = None

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

    def _flush_thumbnail_progress(self) -> None:
        """Coalesced status-bar update — connected to the progress coalescer."""
        from Imervue.gpu_image_view.tile_loader import flush_thumbnail_progress
        flush_thumbnail_progress(self)

    # 保持向後相容（undo_delete 使用）
    def add_thumbnail(self, img_data, path, generation=None):
        """Insert a thumbnail directly — external contract (undo_delete)."""
        from Imervue.gpu_image_view.tile_loader import add_thumbnail
        add_thumbnail(self, img_data, path, generation)

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

    def load_deep_zoom_image(self, path):
        # Capture whether this image was *genuinely* remembered BEFORE the save
        # below — `_save_view_state` writes the (already-updated) current index,
        # which would otherwise pre-seed this path with the previous view's
        # leftover zoom and fool the fit-on-load decision into skipping the fit.
        self._loading_was_remembered = path in self._view_memory
        # 儲存前一張的狀態
        self._save_view_state()

        self._cancel_deep_zoom_worker()
        self._clear_deep_zoom()

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
            if self._should_refit_on_load():
                self._fit_to_window()
            self._init_animation(path)
            self._prefetch_neighbors()
            self._update_status_info()
            self._notify_deep_zoom_displayed()
            self._browse.begin_image_fade_in()
            self.update()
            return

        # ===== 快取未命中 → 背景載入（顯示載入指示，避免空白幀）=====
        self._deep_zoom_loading = path
        if self._prefetch.has_worker(path):
            self.update()
            return

        from Imervue.image.recipe_store import recipe_store
        recipe = recipe_store.get_for_path(path)
        worker = LoadDeepZoomWorker(path, recipe=recipe)
        worker.signals.finished.connect(self._on_deep_zoom_loaded)
        self.active_deep_zoom_worker = worker
        self.deepzoom_pool.start(worker)

        if hasattr(self.main_window, 'set_status'):
            self.main_window.set_status(
                self.main_window.language_wrapper.language_word_dict.get(
                    "status_loading_image", "Loading image..."
                )
            )

        self.update()

    def _on_deep_zoom_loaded(self, dzi, path):
        if (not self.model.images
                or self.current_index >= len(self.model.images)
                or self.model.images[self.current_index] != path):
            return

        self.deep_zoom = dzi
        self.tile_manager = TileManager(dzi)
        self.active_deep_zoom_worker = None

        # 首次進入此圖片 → 自動 fit-to-window
        cur_path = self.model.images[self.current_index]
        if cur_path and self._should_refit_on_load():
            self._fit_to_window()

        # 動畫偵測
        self._init_animation(path)

        self._prefetch_neighbors()

        if hasattr(self.main_window, 'set_status'):
            self.main_window.set_status(
                self.main_window.language_wrapper.language_word_dict.get(
                    "status_ready", "Ready"
                )
            )

        self._update_status_info()
        self._notify_deep_zoom_displayed()
        self._browse.begin_image_fade_in()
        self.update()

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
        if (self.deep_zoom is None
                and self.model.images
                and self.current_index < len(self.model.images)
                and self.model.images[self.current_index] == path):
            self.deep_zoom = dzi
            self.tile_manager = TileManager(dzi)
            self._prefetch_neighbors()
            self._browse.begin_image_fade_in()
            self.update()
            return

        # 否則存入預載快取
        self._prefetch.store(path, dzi)

    # ---------------------------
    # 清除 Tile Grid
    # ---------------------------
    def clear_tile_grid(self):
        self._cancel_tile_workers()
        self.tile_grid_mode = False
        self.tile_rects = []
        self._delete_all_tile_textures()
        self.tile_cache.clear()

        self.grid_offset_x = 0
        self.grid_offset_y = 0
        self.focused_tile_index = NO_FOCUS
        self._filmstrip_thumb_cache.clear()
        self._tile_load_times.clear()

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
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if self.tile_grid_mode:
            # 滾輪 → 上下捲動縮圖列表
            scroll_amount = delta / 2  # angleDelta 通常 ±120，/2 → ±60 px
            self.grid_offset_y += scroll_amount
            self._clamp_grid_scroll()
            self.update()
            return
        if (self.deep_zoom and self._loupe_enabled
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            from Imervue.gpu_image_view.overlay_painter import (
                clamp_loupe_magnification,
            )
            self._loupe_magnification = clamp_loupe_magnification(
                self._loupe_magnification, delta)
            self.update()
            return
        if self.deep_zoom and self._reading_mode:
            self._browse.reading_wheel(delta)
            return
        if self.deep_zoom:
            self._input.handle_deep_zoom_wheel(event, delta)

    def _zoom_step(self, zoom_in: bool) -> None:
        """Keyboard zoom in/out — called by the key-action dispatcher.
        External contract, keep the name/signature stable."""
        self._input.zoom_step(zoom_in)

    def _fit_window_with_toast(self) -> None:
        """Fit-to-window + toast — called by the key-action dispatcher.
        External contract, keep the name/signature stable."""
        if self.deep_zoom:
            self._fit_to_window()
            self.update()
            self._toast("fit_window", "Fit to Window")

    def mousePressEvent(self, event):
        self.last_pos = event.position()
        self._cancel_hover_preview()
        # 任何按下都中止進行中的平滑動畫，使用者重新取得控制權。
        self._zoom_ease.stop()
        self._pan_momentum.stop()

        # ===== 中鍵拖動 =====
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = True
            self._last_pan_velocity = (0.0, 0.0)
            return

        # ===== 右鍵 → 顯示選單 =====
        if event.button() == Qt.MouseButton.RightButton:
            right_click_context_menu(
                main_gui=self,
                global_pos=event.globalPosition().toPoint(),
                local_pos=event.position()
            )
            return

        # ===== 左鍵 =====
        if event.button() == Qt.MouseButton.LeftButton:
            if self.tile_grid_mode:
                self._drag_start_pos = event.position()
                self._drag_end_pos = event.position()
                self._drag_selecting = False  # 先不啟動，等拖動才算框選
            elif self.deep_zoom:
                if self._browse.handle_deep_zoom_press(event.position()):
                    return
                self._input.begin_zoom_band(event.position())
            return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Deep zoom: double-click toggles fit ↔ 100% centred on the cursor,
        # except inside the minimap (which owns clicks for navigation).
        if (event.button() == Qt.MouseButton.LeftButton
                and self.deep_zoom and not self.tile_grid_mode):
            pos = event.position()
            rect = self._current_minimap_rect()
            if rect is None or not point_in_rect(pos.x(), pos.y(), rect):
                self._input.toggle_zoom_at(pos)
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        self._input.update_hover_state(event)

        if self.last_pos is None:
            self.last_pos = event.position()
            return

        delta = event.position() - self.last_pos
        self.last_pos = event.position()

        if self._middle_dragging:
            self._input.handle_middle_drag(delta)
            return

        if self._minimap_dragging:
            self._input.minimap_nav_to(event.position())
            return

        if self._zoom_band_active:
            self._input.update_zoom_band(event)
            return

        self._input.handle_left_drag_select(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = False
            self._input.start_pan_momentum()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._minimap_dragging:
            self._minimap_dragging = False
            return
        if (event.button() == Qt.MouseButton.LeftButton
                and self._zoom_band_active):
            self._input.finish_zoom_band(event.position())
            return
        if (
            self.tile_grid_mode
            and event.button() == Qt.MouseButton.LeftButton
            and self._input.handle_tile_release(event)
        ):
            return
        super().mouseReleaseEvent(event)

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
