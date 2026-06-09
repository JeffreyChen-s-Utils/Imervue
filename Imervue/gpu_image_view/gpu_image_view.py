from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from Imervue.gpu_image_view.actions.keyboard_actions import (
    toggle_fullscreen,
)
from Imervue.gpu_image_view.actions.slideshow import stop_slideshow
from Imervue.gpu_image_view.actions.select import (
    switch_to_next_image, switch_to_previous_image, select_tiles_in_rect,
    switch_to_next_folder, switch_to_previous_folder,
)
from Imervue.gpu_image_view.images.image_loader import LoadDeepZoomWorker
from Imervue.gpu_image_view.minimap import (
    minimap_geometry,
    point_in_rect,
    recenter_offsets,
)
from Imervue.gpu_image_view.tile_layout import (
    DEFAULT_THUMBNAIL_SIZE,
    plan_tile_size_change,
    resolve_thumbnail_size,
    tile_grid_layout,
)
from Imervue.gpu_image_view.view_nav import (
    stepped_zoom,
    toggle_zoom_target,
    zoom_about_point,
)
from Imervue.gpu_image_view.images.prefetch import (
    NavigationDirectionTracker,
    compute_prefetch_targets,
    range_for_direction,
)
from Imervue.gpu_image_view.images.image_model import ImageModel
from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker
from Imervue.menu.right_click_menu import right_click_context_menu

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

import numpy as np
import os
from collections import OrderedDict
from OpenGL.GL import (
    GL_BLEND,
    GL_COLOR_BUFFER_BIT,
    GL_LINES,
    GL_LINE_LOOP,
    GL_MODELVIEW,
    GL_NO_ERROR,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_PROJECTION,
    GL_QUADS,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TRIANGLE_FAN,
    GL_UNPACK_ALIGNMENT,
    glBegin,
    glBlendFunc,
    glClear,
    glClearColor,
    glColor4f,
    glDeleteTextures,
    glDisable,
    glEnable,
    glEnd,
    glGetError,
    glGetIntegerv,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPixelStorei,
    glScalef,
    glTranslatef,
    glVertex2f,
    glViewport,
)
from PySide6.QtCore import QThreadPool, QMutex, QMutexLocker, Qt
from PySide6.QtGui import QUndoStack, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from pathlib import Path

from Imervue.gpu_image_view.gl_renderer import GLRenderer
from Imervue.gpu_image_view.texture_upload import prepare_rgba, upload_rgba_texture
from Imervue.image.tile_manager import TileManager
import contextlib

# DeepZoom 預載範圍（±N 張）
_PREFETCH_RANGE = 3
_PREFETCH_MAX = _PREFETCH_RANGE * 2 + 1


def _format_file_size(path: str) -> str:
    """Return a human-readable size for ``path``, or "" if unavailable."""
    try:
        size_bytes = os.path.getsize(path)
    except OSError:
        return ""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / 1024:.1f} KB"


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
        self.tile_textures = {}
        self.tile_cache = {}  # path -> img_data
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
        self._saved_tile_state = None
        # True while the user is click-dragging inside the deep-zoom minimap
        # to pan the viewport.
        self._minimap_dragging = False
        # When True, the user has zoomed / panned manually so the
        # canvas should not auto-fit on resize. Cleared on every
        # fresh image load via :meth:`_fit_to_window`.
        self._user_locked_view = False
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

        # ===== Hover 預覽 =====
        # Lazy-init 避免在沒有 QApplication 時匯入失敗
        self._hover_controller = None
        self._hover_last_path: str | None = None

        # ===== 瀏覽歷史 =====
        # 每次進入 deep zoom 的圖片會被 push 到 _history。
        # _history_pos 指向目前位置；前進/後退移動指標，不重寫 stack
        # (除非使用者跳到新圖，這時會 truncate forward history).
        self._history: list[str] = []
        self._history_pos: int = -1
        self._history_navigating: bool = False  # True → 抑制 push 進 history

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
        self._prefetch_mutex = QMutex()  # 保護 prefetch cache/workers
        self._load_generation = 0  # 世代計數器，用來取消過期的 tile worker
        self.active_tile_workers = []  # 用來追蹤/取消 Tile Grid 載入 worker
        self.active_deep_zoom_worker = None  # 當前 DeepZoom 背景 worker

        # ===== 記憶位置 & 縮放 =====
        self._view_memory: dict[str, dict] = {}  # path → {zoom, dx, dy}

        # ===== Prefetch（DeepZoom 預載入）=====
        self._prefetch_cache: OrderedDict[str, object] = OrderedDict()  # path → DeepZoomImage
        self._prefetch_workers: dict[str, LoadDeepZoomWorker] = {}  # path → worker
        # Track navigation direction so the prefetch window can lean
        # ahead when the user is paging forward and behind when they
        # reverse — see :mod:`prefetch`.
        self._nav_direction_tracker = NavigationDirectionTracker()

        # ===== GL Renderer =====
        self.renderer = GLRenderer()

        # ===== QPainter overlay (OSD / HUD / histogram / badges) =====
        from Imervue.gpu_image_view.overlay_painter import OverlayPainter
        self._overlay = OverlayPainter(self)

        # ===== Keyboard-action dispatch =====
        from Imervue.gpu_image_view.key_action_dispatcher import KeyActionDispatcher
        self._key_dispatch = KeyActionDispatcher(self)

        # ===== VRAM 管理 =====
        # 保守預設 1.5 GB。initializeGL() 會嘗試用 NVX/ATI 擴充詢問 GPU 實際 VRAM，
        # 抓到的話會覆寫成實體 VRAM 的 ~40%，在顯卡強的機器上可大幅放寬 tile cache。
        self._vram_usage = 0  # 目前 tile grid 紋理佔用 bytes
        self._vram_limit = int(1.5 * 1024 * 1024 * 1024)  # 1.5 GB fallback
        self._vram_limit_default = self._vram_limit
        self._tile_tex_sizes: dict[str, int] = {}  # path → texture bytes

        # ===== 直方圖 =====
        self._show_histogram = False
        self._histogram_cache: tuple | None = None  # (path, hist_r, hist_g, hist_b)

        # ===== OSD (On-Screen Display) =====
        # F3 — 切換右上角顯示檔名 / 尺寸 / 格式 / 檔案大小
        self._show_osd = False
        # Ctrl+F3 — Debug HUD：VRAM、tile cache、執行緒池等技術資訊
        self._show_debug_hud = False
        # 目前滑鼠在圖片上的像素座標（update_status 用，paint_pixel_view 用）
        self._hover_image_xy: tuple[int, int] | None = None
        # Shift+P — 像素檢視模式：zoom >= 4x 時顯示像素網格 + RGB 值
        self._pixel_view = False

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
        with contextlib.suppress(Exception):
            self._prefetch_cache.pop(path, None)
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
        """Query the GL driver for real VRAM and size the tile cache to it.

        * NVIDIA: ``GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX`` (0x9048), KB.
        * AMD:    ``TEXTURE_FREE_MEMORY_ATI`` (0x87FC), KB, 4-int vector (we
          take the first — total free pool).

        Fall back to the conservative 1.5 GB default on Intel / software GL
        or any driver that doesn't expose either extension. The detected
        limit is clamped to ``[256 MB, 8 GB]`` so a bad query can't blow up
        memory or accidentally disable the cache.

        A user override (Preferences > VRAM limit) takes precedence — if
        ``vram_limit_auto`` is ``False`` in user settings the user's value
        is used as-is and no driver probing happens.
        """
        import logging as _logging
        _log = _logging.getLogger("Imervue.vram")

        if self._apply_user_vram_override(_log):
            return

        total_kb = self._probe_vendor_vram_kb()
        self._drain_gl_error_queue()

        if total_kb <= 0:
            _log.info(
                f"VRAM detection not supported on this driver, using default "
                f"{self._vram_limit_default // (1024 * 1024)} MB"
            )
            return

        from Imervue.gpu_image_view.vram_budget import clamp_detected_bytes
        total_bytes = total_kb * 1024
        detected = clamp_detected_bytes(int(total_bytes * 0.4))
        self._vram_limit = detected
        _log.info(
            f"Detected VRAM {total_bytes // (1024 * 1024)} MB → tile cache "
            f"limit set to {detected // (1024 * 1024)} MB"
        )

    def _apply_user_vram_override(self, log) -> bool:
        """Apply a user-configured VRAM limit, returning True when honoured.

        Delegates to ``vram_budget.compute_user_override_bytes`` which
        handles the auto/explicit toggle and clamping. Returns True when
        an override was applied (caller should skip driver probing).
        """
        from Imervue.gpu_image_view.vram_budget import compute_user_override_bytes
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        override = compute_user_override_bytes(user_setting_dict)
        if override is None:
            return False
        self._vram_limit = override
        log.info(
            f"User-configured VRAM tile cache limit: {override // (1024 * 1024)} MB"
        )
        return True

    def _probe_vendor_vram_kb(self) -> int:
        """Try NVX (NVIDIA) then ATI (AMD) VRAM probes, return KB or 0."""
        # NVIDIA: GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX
        kb = self._probe_gl_integer(0x9048)
        if kb > 0:
            return kb
        # AMD: TEXTURE_FREE_MEMORY_ATI (4-int vector, take total free pool)
        return self._probe_gl_integer(0x87FC)

    @staticmethod
    def _probe_gl_integer(enum: int) -> int:
        """Read an integer (or first element of a vector) from glGetIntegerv."""
        try:
            val = glGetIntegerv(enum)
        except Exception:
            return 0
        if isinstance(val, (list, tuple)):
            return int(val[0]) if val else 0
        return int(val) if val is not None else 0

    @staticmethod
    def _drain_gl_error_queue() -> None:
        """Clear any GL error left by extension probes that aren't supported."""
        with contextlib.suppress(Exception):
            # glGetError has the side-effect of clearing the flag.
            while glGetError() != GL_NO_ERROR:  # noqa: S108
                continue

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

        # ===== Tile Grid Mode =====
        if self.tile_grid_mode:
            self.paint_tile_grid()
        # ===== DeepZoom Mode =====
        elif self.deep_zoom:
            self.paint_deep_zoom()
            self._paint_minimap()

        painter.endNativePainting()

        # ===== QPainter 文字/圖形覆蓋層 =====
        self._paint_overlay(painter)
        painter.end()

    # ---------------------------
    # Tile Grid Lazy Render
    # ---------------------------
    def _tile_base_size(self) -> int:
        if self.thumbnail_size is not None:
            return self.thumbnail_size
        if self.tile_cache:
            # 用第一張圖實際寬度當排版基準
            return next(iter(self.tile_cache.values())).shape[1]
        return 256

    def _draw_tile_placeholder(self, x0: float, y0: float,
                               scaled_tile: float, vw: int, vh: int) -> None:
        x1, y1 = x0 + scaled_tile, y0 + scaled_tile
        if x1 < 0 or x0 > vw or y1 < 0 or y0 > vh:
            return
        self.renderer.draw_colored_rect(x0, y0, x1, y1,
                                        0.14, 0.14, 0.14, 1.0, filled=True)
        self.renderer.draw_colored_rect(x0, y0, x1, y1,
                                        0.28, 0.28, 0.28, 1.0, filled=False)
        self.placeholder_rects.append((x0, y0, x1, y1))

    def _ensure_tile_texture(self, path: str, img_data) -> bool:
        """Allocate a GPU texture for *path* if needed. Returns False when
        over the VRAM budget so the caller can skip drawing.

        Generates the full mipmap chain at upload time so the
        trilinear minification filter has every level it needs.
        At small zooms the GPU samples a small mip level instead
        of the 1024²-ish base, cutting sampling cost by ~33 % and
        eliminating the moire / sparkle that bare GL_LINEAR shows
        on downscaled tiles.
        """
        if path in self.tile_textures:
            return True
        from Imervue.gpu_image_view.vram_budget import mipmap_texture_bytes
        tex_bytes = mipmap_texture_bytes(
            img_data.shape[1], img_data.shape[0],
        )
        if self._vram_usage + tex_bytes > self._vram_limit:
            return False
        tex = upload_rgba_texture(
            prepare_rgba(img_data),
            generate_mipmaps=True,
            uploader=self._tile_uploader,
        )
        self.tile_textures[path] = tex
        self._tile_tex_sizes[path] = tex_bytes
        self._vram_usage += tex_bytes
        return True

    def _draw_single_tile(self, i: int, path: str, cols: int, cell: float,
                          scaled_tile: float, vw: int, vh: int) -> None:
        row, col = divmod(i, cols)
        x0 = col * cell + self.grid_offset_x
        y0 = row * cell + self.grid_offset_y
        if path not in self.tile_cache:
            self._draw_tile_placeholder(x0, y0, scaled_tile, vw, vh)
            return
        img_data = self.tile_cache[path]
        x1 = x0 + img_data.shape[1] * self._tile_draw_scale
        y1 = y0 + img_data.shape[0] * self._tile_draw_scale
        if x1 < 0 or x0 > vw or y1 < 0 or y0 > vh:
            return
        self.tile_rects.append((x0, y0, x1, y1, path))
        if not self._ensure_tile_texture(path, img_data):
            return
        self.renderer.draw_textured_quad(x0, y0, x1, y1,
                                         self.tile_textures[path])

    def _draw_tile_grid_borders(self) -> None:
        if not self.tile_rects:
            return
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1)
        for x0, y0, x1, y1, _path in self.tile_rects:
            self.renderer.draw_colored_rect(x0, y0, x1, y1,
                                            0.3, 0.3, 0.3, 1.0, filled=False)
        glEnable(GL_TEXTURE_2D)

    def _draw_tile_selection_marker(self, x0, y0, x1, y1) -> None:
        # 藍色粗邊框
        glColor4f(0.18, 0.5, 1.0, 1.0)
        glBegin(GL_LINE_LOOP)
        for (vx, vy) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            glVertex2f(vx, vy)
        glEnd()
        # 右上藍色圓 + 勾
        circle_radius = 9
        cx, cy = x1 - 12, y0 + 12
        glBegin(GL_TRIANGLE_FAN)
        glVertex2f(cx, cy)
        for i in range(33):
            angle = i * 2.0 * 3.1415926 / 32
            glVertex2f(cx + circle_radius * np.cos(angle),
                       cy + circle_radius * np.sin(angle))
        glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glLineWidth(2.5)
        glBegin(GL_LINES)
        glVertex2f(cx - 4, cy)
        glVertex2f(cx - 1, cy + 3)
        glVertex2f(cx - 1, cy + 3)
        glVertex2f(cx + 5, cy - 4)
        glEnd()
        glLineWidth(4)

    def _draw_tile_selection_overlay(self) -> None:
        if not self.tile_selection_mode:
            return
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glLineWidth(4)
        for x0, y0, x1, y1, path in self.tile_rects:
            if path in self.selected_tiles:
                self._draw_tile_selection_marker(x0, y0, x1, y1)
        glDisable(GL_BLEND)
        glEnable(GL_TEXTURE_2D)
        glColor4f(1, 1, 1, 1)
        glLineWidth(1)

    def _draw_drag_select_rect(self) -> None:
        if not (self._drag_selecting and self._drag_start_pos
                and self._drag_end_pos):
            return
        x0, y0 = self._drag_start_pos.x(), self._drag_start_pos.y()
        x1, y1 = self._drag_end_pos.x(), self._drag_end_pos.y()
        left, right = min(x0, x1), max(x0, x1)
        top, bottom = min(y0, y1), max(y0, y1)
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # 淡藍填充
        glColor4f(0.18, 0.5, 1.0, 0.08)
        glBegin(GL_QUADS)
        for (vx, vy) in ((left, top), (right, top), (right, bottom), (left, bottom)):
            glVertex2f(vx, vy)
        glEnd()
        # 藍色粗框
        glColor4f(0.18, 0.5, 1.0, 1.0)
        glLineWidth(3)
        glBegin(GL_LINE_LOOP)
        for (vx, vy) in ((left, top), (right, top), (right, bottom), (left, bottom)):
            glVertex2f(vx, vy)
        glEnd()
        glDisable(GL_BLEND)
        glEnable(GL_TEXTURE_2D)
        glColor4f(1, 1, 1, 1)

    def paint_tile_grid(self):
        glLoadIdentity()

        # 預先淘汰超出 VRAM 上限的紋理（不在逐 tile 迴圈中做）
        self._evict_tile_textures_if_needed()

        images = self.model.images
        base_tile = self._tile_base_size()
        self._tile_draw_scale, cell, cols = tile_grid_layout(
            self.width(), base_tile, self.tile_scale,
            self.tile_padding, self.devicePixelRatio(),
        )
        scaled_tile = base_tile * self._tile_draw_scale
        self.tile_rects = []
        # Placeholders for tiles whose thumbnail hasn't arrived yet — rendered
        # as dark squares so the grid layout is visible immediately. Stored
        # in screen coords; consumed by ``_draw_tile_placeholders`` overlay.
        self.placeholder_rects: list[tuple[float, float, float, float]] = []

        # 在迴圈外設定一次 GL 狀態，避免每張 tile 都重複呼叫
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        vw, vh = self.width(), self.height()

        for i, path in enumerate(images):
            self._draw_single_tile(i, path, cols, cell, scaled_tile, vw, vh)

        self._draw_tile_grid_borders()
        self._draw_tile_selection_overlay()
        self._draw_drag_select_rect()

    # ---------------------------
    # DeepZoom Lazy Render
    # ---------------------------
    def paint_deep_zoom(self):
        if not self.deep_zoom:
            return

        if self._slideshow_opacity < 1.0:
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        level, _ = self.deep_zoom.get_level(self.zoom)
        level_image = self.deep_zoom.levels[level]
        base_image = self.deep_zoom.levels[0]
        scale_x = self.zoom * (base_image.shape[1] / level_image.shape[1])
        scale_y = self.zoom * (base_image.shape[0] / level_image.shape[0])

        self._apply_deep_zoom_transform(scale_x, scale_y)
        self._draw_visible_deep_zoom_tiles(level, level_image, scale_x, scale_y)

        # 恢復 ortho MVP for other rendering
        if self.renderer.use_shaders:
            self.renderer.set_ortho(self.width(), self.height())

    def _apply_deep_zoom_transform(self, scale_x: float, scale_y: float) -> None:
        """Push the scale+translate matrix that maps deep-zoom tile
        coordinates into widget pixels — shader path or fixed-function."""
        if self.renderer.use_shaders:
            import numpy as _np
            from Imervue.gpu_image_view.gl_renderer import _ortho
            base_ortho = _ortho(0, self.width(), self.height(), 0, -1, 1)
            trans = _np.eye(4, dtype=_np.float32)
            trans[3, 0] = self.dz_offset_x / scale_x
            trans[3, 1] = self.dz_offset_y / scale_y
            scl = _np.eye(4, dtype=_np.float32)
            scl[0, 0] = scale_x
            scl[1, 1] = scale_y
            self.renderer.set_mvp(trans @ scl @ base_ortho)
            return
        glLoadIdentity()
        glScalef(scale_x, scale_y, 1)
        glTranslatef(self.dz_offset_x / scale_x, self.dz_offset_y / scale_y, 0)

    def _draw_visible_deep_zoom_tiles(
        self, level: int, level_image, scale_x: float, scale_y: float,
    ) -> None:
        """Walk the deep-zoom level and draw every tile that overlaps
        the current viewport, fetching textures lazily."""
        tile_size = self.deep_zoom_tile_size
        h, w = level_image.shape[:2]

        left = -self.dz_offset_x / scale_x
        top = -self.dz_offset_y / scale_y
        right = left + self.width() / scale_x
        bottom = top + self.height() / scale_y

        tx0 = int(left // tile_size)
        tx1 = int(right // tile_size)
        ty0 = int(top // tile_size)
        ty1 = int(bottom // tile_size)

        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                self._draw_one_deep_zoom_tile(level, tx, ty, tile_size, w, h)

    def _draw_one_deep_zoom_tile(
        self, level: int, tx: int, ty: int, tile_size: int, w: int, h: int,
    ) -> None:
        """Draw a single deep-zoom tile if it lies inside the level's
        bounds and its texture is ready."""
        if not (0 <= tx * tile_size < w and 0 <= ty * tile_size < h):
            return
        tex = self.tile_manager.get_tile(level, tx, ty, tile_size)
        if tex is None:
            return
        tile_w = min(tile_size, w - tx * tile_size)
        tile_h = min(tile_size, h - ty * tile_size)
        x = tx * tile_size
        y = ty * tile_size
        self.renderer.draw_textured_quad(
            x, y, x + tile_w, y + tile_h, tex, self._slideshow_opacity,
        )

    # ---------------------------
    # 小地圖（Deep Zoom）
    # ---------------------------
    _MINIMAP_OPACITY = 0.85

    def _current_minimap_rect(self) -> tuple[int, int, int, int] | None:
        """Minimap rectangle (x, y, w, h) in widget coords, or None when no
        deep-zoom image is loaded. Shared by the painter and the click handler
        so the clickable area always matches what is drawn."""
        if not self.deep_zoom:
            return None
        base = self.deep_zoom.levels[0]
        return minimap_geometry(
            self.width(), self.height(), base.shape[1], base.shape[0],
        )

    def _paint_minimap(self):
        rect = self._current_minimap_rect()
        if rect is None:
            return

        base = self.deep_zoom.levels[0]
        img_w, img_h = base.shape[1], base.shape[0]
        mm_x, mm_y, mm_w, mm_h = rect

        # 確保 ortho 回到畫面座標
        if not self.renderer.use_shaders:
            glLoadIdentity()

        # --- 半透明背景 ---
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.renderer.draw_colored_rect(
            mm_x - 2, mm_y - 2, mm_x + mm_w + 2, mm_y + mm_h + 2,
            0.0, 0.0, 0.0, 0.5,
        )

        # --- 縮圖紋理（用最低解析度 level）---
        thumb = self.deep_zoom.levels[-1]
        if self._minimap_dzi is not self.deep_zoom:
            # 重建 minimap texture
            if self._minimap_tex is not None:
                glDeleteTextures([self._minimap_tex])
            self._minimap_tex = upload_rgba_texture(
                prepare_rgba(thumb), clamp_to_edge=False,
            )
            self._minimap_dzi = self.deep_zoom

        self.renderer.draw_textured_quad(mm_x, mm_y, mm_x + mm_w, mm_y + mm_h,
                                         self._minimap_tex)

        # --- viewport 指示框 ---
        # 畫面可視區域在原圖座標
        vp_left = -self.dz_offset_x / self.zoom
        vp_top = -self.dz_offset_y / self.zoom
        vp_right = vp_left + self.width() / self.zoom
        vp_bottom = vp_top + self.height() / self.zoom

        # 映射到小地圖座標
        sx = mm_w / img_w
        sy = mm_h / img_h
        rx0 = mm_x + max(0, vp_left * sx)
        ry0 = mm_y + max(0, vp_top * sy)
        rx1 = mm_x + min(mm_w, vp_right * sx)
        ry1 = mm_y + min(mm_h, vp_bottom * sy)

        # 白色框線
        self.renderer.draw_colored_rect(rx0, ry0, rx1, ry1,
                                         1.0, 1.0, 1.0, 0.8, filled=False)
        glDisable(GL_BLEND)

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
    # Status bar sync
    # ---------------------------
    def _update_status_info(self):
        """Push current image / zoom / cursor info to the main-window status bar."""
        mw = self.main_window
        if not hasattr(mw, "update_status_info"):
            return
        images = self.model.images
        idx = self.current_index

        if not self.deep_zoom or not images or idx >= len(images):
            self._update_status_info_no_image(mw, images, idx)
            return

        path = images[idx]
        base = self.deep_zoom.levels[0]
        h, w = base.shape[:2]

        from Imervue.user_settings.color_labels import get_color_label
        mw.update_status_info(
            index=f"{idx + 1}/{len(images)}",
            resolution=f"{w}×{h}",
            size=_format_file_size(path),
            zoom=f"{self.zoom * 100:.0f}%",
            cursor=self._format_cursor(w, h),
            label=get_color_label(path) or "",
        )

    def _update_status_info_no_image(self, mw, images: list[str], idx: int) -> None:
        """Status-bar update path for tile-grid / unloaded-image states."""
        if not images:
            mw.clear_status_info()
            return
        index_text = (
            f"{idx + 1}/{len(images)}" if self.deep_zoom
            else f"— / {len(images)}"
        )
        mw.update_status_info(
            index=index_text,
            resolution="", size="", zoom="", cursor="",
        )

    def _format_cursor(self, w: int, h: int) -> str:
        if self._hover_image_xy is None:
            return ""
        cx, cy = self._hover_image_xy
        if 0 <= cx < w and 0 <= cy < h:
            return f"x={cx}, y={cy}"
        return ""

    # ---------------------------
    # Fit to Window
    # ---------------------------
    def _fit_zoom(self) -> float:
        """Zoom level that fits the whole image in the canvas (capped at 1.0).

        Prefers the most recent ``resizeGL`` size — it's authoritative for the
        GL coordinate system and avoids the brief frames where ``self.width()``
        lags the actual layout.
        """
        base = self.deep_zoom.levels[0]
        img_w, img_h = base.shape[1], base.shape[0]
        if self._last_resize_size != (0, 0):
            w, h = self._last_resize_size
        else:
            w, h = self.width() or 1, self.height() or 1
        return min(w / img_w, h / img_h, 1.0)

    def _fit_to_window(self):
        """自動縮放使圖片完整顯示在視窗內"""
        if not self.deep_zoom:
            return
        base = self.deep_zoom.levels[0]
        img_w, img_h = base.shape[1], base.shape[0]
        if self._last_resize_size != (0, 0):
            w, h = self._last_resize_size
        else:
            w, h = self.width() or 1, self.height() or 1
        self.zoom = self._fit_zoom()
        displayed_w = img_w * self.zoom
        displayed_h = img_h * self.zoom
        self.dz_offset_x = (w - displayed_w) / 2
        self.dz_offset_y = (h - displayed_h) / 2
        # Fresh fit → user hasn't panned / zoomed yet, so subsequent
        # resizes (docks settling, window maximised) keep the image
        # centred instead of hanging off-screen.
        self._user_locked_view = False

    def _fit_to_width(self):
        """縮放使圖片寬度填滿視窗"""
        if not self.deep_zoom:
            return
        base = self.deep_zoom.levels[0]
        img_w, img_h = base.shape[1], base.shape[0]
        w, h = self.width() or 1, self.height() or 1
        self.zoom = w / img_w
        displayed_h = img_h * self.zoom
        self.dz_offset_x = 0
        self.dz_offset_y = (h - displayed_h) / 2
        self.update()

    def _fit_to_height(self):
        """縮放使圖片高度填滿視窗"""
        if not self.deep_zoom:
            return
        base = self.deep_zoom.levels[0]
        img_w, img_h = base.shape[1], base.shape[0]
        w, h = self.width() or 1, self.height() or 1
        self.zoom = h / img_h
        displayed_w = img_w * self.zoom
        self.dz_offset_x = (w - displayed_w) / 2
        self.dz_offset_y = 0
        self.update()

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
        """從剪貼簿貼上圖片，儲存到目前資料夾並載入"""
        clipboard = QApplication.clipboard()
        qimg = clipboard.image()
        if qimg.isNull():
            self._open_clipboard_url_if_any(clipboard)
            return

        folder = self._resolve_paste_target_folder()
        if folder is None:
            return

        save_path = self._save_clipboard_image(qimg, folder)
        self._load_pasted_image(save_path)

    def _open_clipboard_url_if_any(self, clipboard) -> None:
        """If the clipboard holds a file URL, open it in the viewer."""
        mime = clipboard.mimeData()
        if not (mime and mime.hasUrls()):
            return
        for url in mime.urls():
            p = url.toLocalFile()
            if p and Path(p).is_file():
                from Imervue.gpu_image_view.images.image_loader import open_path
                open_path(main_gui=self, path=p)
                return

    def _resolve_paste_target_folder(self) -> str | None:
        """Pick the folder where a pasted clipboard image should land."""
        images = self.model.images
        if images:
            folder = str(Path(images[0]).parent)
        else:
            from Imervue.user_settings.user_setting_dict import user_setting_dict
            folder = user_setting_dict.get("user_last_folder", "")
        if not folder or not Path(folder).is_dir():
            return None
        return folder

    def _save_clipboard_image(self, qimg, folder: str) -> str:
        """Persist ``qimg`` under ``folder`` with a timestamped name."""
        import time
        name = f"pasted_{int(time.time())}.png"
        save_path = str(Path(folder) / name)
        qimg.save(save_path, "PNG")
        return save_path

    def _load_pasted_image(self, save_path: str) -> None:
        """Insert the saved file into the model and open it in the viewer."""
        images = self.model.images
        if save_path not in images:
            images.append(save_path)
            images.sort(key=lambda p: os.path.basename(p).lower())

        from Imervue.gpu_image_view.images.image_loader import open_path
        open_path(main_gui=self, path=save_path)

        if hasattr(self.main_window, 'toast'):
            self.main_window.toast.info(f"Pasted: {Path(save_path).name}")

    # ===========================
    # 載入管理
    # ===========================
    def _evict_tile_textures_if_needed(self):
        """VRAM 超出上限時淘汰不在視窗內的紋理（在 paint 前呼叫）"""
        if self._vram_usage <= self._vram_limit:
            return
        visible = self._compute_visible_tile_paths()
        self._evict_invisible_tile_textures(visible)

    def _evict_base_tile_size(self) -> int:
        """Return the tile-grid cell base size for visibility computation."""
        if self.model.images and self.thumbnail_size is not None:
            return self.thumbnail_size
        if self.tile_cache:
            return next(iter(self.tile_cache.values())).shape[1]
        return 256

    def _compute_visible_tile_paths(self) -> set[str]:
        """Return the subset of cached tiles whose rect intersects the viewport."""
        images = self.model.images
        base_tile = self._evict_base_tile_size()
        draw_scale, cell, cols = tile_grid_layout(
            self.width(), base_tile, self.tile_scale,
            self.tile_padding, self.devicePixelRatio(),
        )
        vw, vh = self.width(), self.height()

        visible: set[str] = set()
        for i, p in enumerate(images):
            if p not in self.tile_cache:
                continue
            row, col = divmod(i, cols)
            x0 = col * cell + self.grid_offset_x
            y0 = row * cell + self.grid_offset_y
            img = self.tile_cache[p]
            x1 = x0 + img.shape[1] * draw_scale
            y1 = y0 + img.shape[0] * draw_scale
            if x1 >= 0 and x0 <= vw and y1 >= 0 and y0 <= vh:
                visible.add(p)
        return visible

    def _evict_invisible_tile_textures(self, visible: set[str]) -> None:
        """Delete GPU textures for paths not in ``visible`` until under VRAM cap."""
        # list() required because we mutate the dict inside the loop.
        for p in list(self.tile_textures):  # noqa: S7504
            if self._vram_usage <= self._vram_limit:
                return
            if p not in visible:
                glDeleteTextures([self.tile_textures.pop(p)])
                self._vram_usage -= self._tile_tex_sizes.pop(p, 0)

    def _delete_all_tile_textures(self):
        if self.tile_textures:
            glDeleteTextures(list(self.tile_textures.values()))
            self.tile_textures.clear()
        self._tile_tex_sizes.clear()
        self._vram_usage = 0

    def _clear_deep_zoom(self):
        """釋放 DeepZoom 相關的 GPU 與記憶體資源"""
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
        """取消所有預載 worker 並清空快取"""
        for w in self._prefetch_workers.values():
            with contextlib.suppress(RuntimeError, TypeError):
                w.signals.finished.disconnect()
            w.abort()
        self._prefetch_workers.clear()
        self._prefetch_cache.clear()
        # Folder change → forget the previous folder's navigation
        # history so the new folder starts with a symmetric window.
        self._nav_direction_tracker.reset()

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
        self._cancel_tile_workers()
        self._cancel_deep_zoom_worker()
        self._cancel_all_prefetch()
        self._load_generation += 1
        gen = self._load_generation

        self.model.set_images(image_paths)

        self.tile_cache.clear()
        self._delete_all_tile_textures()
        self._clear_deep_zoom()

        self.tile_grid_mode = True
        self._tile_load_total = len(image_paths)
        self._tile_load_count = 0

        from Imervue.gpu_image_view.worker_pools import priority_for_distance
        for index, path in enumerate(image_paths):
            worker = LoadThumbnailWorker(path, self.thumbnail_size, gen)
            worker.signals.finished.connect(self._on_thumbnail_loaded)
            self.active_tile_workers.append(worker)
            # Tiles near the current selection get higher priority
            # so a fresh folder-open shows the user's viewport first
            # even if the pool can't drain the full list before
            # they start scrolling.
            distance = abs(index - self.current_index)
            self.thumbnail_pool.start(worker, priority_for_distance(distance))

        if hasattr(self.main_window, 'show_progress'):
            self.main_window.show_progress(0, self._tile_load_total)

        # 同步 list view（若處於 list 模式或之後會切換）
        if hasattr(self.main_window, "refresh_list_view"):
            with contextlib.suppress(Exception):
                self.main_window.refresh_list_view()

        self.update()

    def _on_thumbnail_loaded(self, img_data, path, generation):
        if generation != self._load_generation:
            return
        if path not in self.model.images:
            return
        with QMutexLocker(self.grid_mutex):
            self.tile_cache[path] = img_data

        self._tile_load_count = len(self.tile_cache)
        # Coalesce the progress update — a folder of N thumbnails
        # finishing in quick succession otherwise re-lays out the
        # status bar N times. The coalescer caps that at one
        # update per ~16 ms; the final flush below makes sure the
        # bar lands at 100 % even if the last tile arrived inside
        # the window.
        self._progress_coalescer.schedule()
        if self._tile_load_count >= self._tile_load_total:
            self._progress_coalescer.force_flush()

        self.update()

    def _flush_thumbnail_progress(self) -> None:
        """Coalesced status-bar update. Reads the latest counter
        and forwards to the main window; called at most once per
        coalescer window."""
        if hasattr(self.main_window, 'show_progress'):
            self.main_window.show_progress(
                self._tile_load_count, self._tile_load_total,
            )

    # 保持向後相容（undo_delete 使用）
    def add_thumbnail(self, img_data, path, generation=None):
        if generation is not None and generation != self._load_generation:
            return
        if path not in self.model.images:
            return
        self.tile_cache[path] = img_data
        self.update()

    # ---------------------------
    # DeepZoom 非同步載入 + 預載
    # ---------------------------
    # ---------------------------
    # Hover preview
    # ---------------------------
    def _ensure_hover_controller(self):
        if self._hover_controller is None:
            from Imervue.gui.hover_preview import HoverPreviewController
            self._hover_controller = HoverPreviewController()
        return self._hover_controller

    def _update_hover_preview(self, event) -> None:
        """Detect which tile (if any) sits under the cursor and arm the popup."""
        # Skip while the user is actively dragging or selecting — popup would
        # get in the way of the drag-select rectangle
        if self._drag_selecting or self._middle_dragging or self._drag_start_pos:
            self._cancel_hover_preview()
            return

        mx, my = event.position().x(), event.position().y()
        hovered_path: str | None = None
        for x0, y0, x1, y1, path in self.tile_rects:
            if x0 <= mx <= x1 and y0 <= my <= y1:
                hovered_path = path
                break

        if hovered_path is None:
            self._cancel_hover_preview()
            return

        if hovered_path != self._hover_last_path:
            self._hover_last_path = hovered_path
            ctrl = self._ensure_hover_controller()
            ctrl.arm(hovered_path, event.globalPosition().toPoint())

    def _cancel_hover_preview(self) -> None:
        self._hover_last_path = None
        if self._hover_controller is not None:
            self._hover_controller.disarm()

    def leaveEvent(self, event):
        self._cancel_hover_preview()
        super().leaveEvent(event)

    # ---------------------------
    # 瀏覽歷史 (Alt+←/→)
    # ---------------------------
    _HISTORY_MAX = 200

    def _push_history(self, path: str) -> None:
        """Append a new image to the history unless we're navigating.

        If the user is in the middle of history (has gone back) and picks a
        new image manually, that truncates the forward entries — matches
        browser behaviour and avoids a broken forward button.
        """
        if self._history_navigating or not path:
            return
        # Deduplicate adjacent entries (reloads shouldn't double-push)
        if (
            self._history
            and self._history_pos >= 0
            and self._history[self._history_pos] == path
        ):
            return
        # Drop forward history when branching
        if self._history_pos < len(self._history) - 1:
            del self._history[self._history_pos + 1:]
        self._history.append(path)
        # Cap size
        if len(self._history) > self._HISTORY_MAX:
            overflow = len(self._history) - self._HISTORY_MAX
            del self._history[:overflow]
            self._history_pos = len(self._history) - 1
        else:
            self._history_pos = len(self._history) - 1

    def history_back(self) -> bool:
        """Jump to the previous image in history. Returns True on success."""
        if self._history_pos <= 0:
            return False
        self._history_pos -= 1
        self._navigate_to_history()
        return True

    def history_forward(self) -> bool:
        """Jump to the next image in history. Returns True on success."""
        if self._history_pos >= len(self._history) - 1:
            return False
        self._history_pos += 1
        self._navigate_to_history()
        return True

    def _navigate_to_history(self) -> None:
        """Load the image at ``_history_pos`` without re-pushing to stack."""
        path = self._history[self._history_pos]
        if not Path(path).is_file():
            return
        images = self.model.images
        if path in images:
            self.current_index = images.index(path)
        self._history_navigating = True
        try:
            self._clear_deep_zoom()
            self.tile_grid_mode = False
            self.load_deep_zoom_image(path)
        finally:
            self._history_navigating = False

    # ---------------------------
    # 顏色標籤 (F1-F5)
    # ---------------------------
    def _apply_color_label(self, color: str) -> None:
        """Toggle ``color`` on the currently-active target(s).

        Priority:
          1. Tile selection mode (multiple tiles selected) → apply to all.
          2. Deep zoom → apply to the visible image.
          3. Tile grid with no selection → apply to the image under cursor,
             or no-op if no tile is hovered.
        """
        from Imervue.user_settings.color_labels import toggle_color_label, set_color_label

        targets = self._resolve_cull_targets()
        if not targets:
            return

        # Single-target behaves as toggle; multi-target applies uniformly.
        if len(targets) == 1:
            new_color = toggle_color_label(targets[0], color)
            self._toast_color_change(targets[0], new_color)
        else:
            for p in targets:
                set_color_label(p, color)
            self._toast_color_batch(color, len(targets))
        # Status bar should reflect the new label for the deep-zoomed image
        if self.deep_zoom:
            self._update_status_info()
        self.update()

    # ---------------------------
    # 分揀 (Culling: Pick / Reject / Unflag)
    # ---------------------------
    _CULL_FALLBACKS = {
        "pick": "Picked {n} image(s)",
        "reject": "Rejected {n} image(s)",
        "unflagged": "Unflagged {n} image(s)",
    }

    def _resolve_cull_targets(self) -> list[str]:
        if (self.tile_grid_mode and self.tile_selection_mode
                and self.selected_tiles):
            return list(self.selected_tiles)
        if self.deep_zoom:
            images = self.model.images
            if images and 0 <= self.current_index < len(images):
                return [images[self.current_index]]
        if self.tile_grid_mode and self._hover_last_path:
            return [self._hover_last_path]
        return []

    def _apply_cull_state(self, state: str) -> None:
        """Apply a cull state to the currently-active target(s).

        Mirrors ``_apply_color_label`` resolution order: multi-selected tiles
        → deep-zoom image → hovered tile.
        """
        from Imervue.library import image_index

        targets = self._resolve_cull_targets()
        if not targets:
            return

        for p in targets:
            image_index.set_cull_state(p, state)

        if hasattr(self.main_window, "toast"):
            lang = self.main_window.language_wrapper.language_word_dict
            fallback = self._CULL_FALLBACKS[state]
            msg = lang.get(f"cull_toast_{state}", fallback).format(n=len(targets))
            self.main_window.toast.info(msg)
        if self.deep_zoom and hasattr(self, "_update_status_info"):
            self._update_status_info()
        self.update()

    def _toast_color_change(self, path: str, new_color: str | None) -> None:
        if not hasattr(self.main_window, "toast"):
            return
        lang = self.main_window.language_wrapper.language_word_dict
        if new_color is None:
            self.main_window.toast.info(
                lang.get("color_label_cleared", "Colour label cleared")
            )
            return
        label = lang.get(f"color_label_{new_color}", new_color.title())
        self.main_window.toast.info(
            lang.get("color_label_set", "Colour: {color}").format(color=label)
        )

    def _toast_color_batch(self, color: str, count: int) -> None:
        if not hasattr(self.main_window, "toast"):
            return
        lang = self.main_window.language_wrapper.language_word_dict
        label = lang.get(f"color_label_{color}", color.title())
        self.main_window.toast.info(
            lang.get("color_label_batch", "{count} images → {color}")
                .format(count=count, color=label)
        )

    # ---------------------------
    # 隨機圖片 (X)
    # ---------------------------
    def jump_to_random_image(self) -> None:
        """Jump to a random image in the current list, avoiding re-pick if possible.

        Uses ``random.choice`` deliberately — this is a UI navigation feature
        (the X-key shortcut "show me a random photo"), not a security-sensitive
        operation. There is no token / nonce / cryptographic context here, so
        an unpredictable PRNG is unnecessary and would only add overhead.
        """
        import random  # nosec B311  # NOSONAR S2245 UI navigation, not security-sensitive
        images = self.model.images
        if not images:
            return
        if len(images) == 1:
            self.current_index = 0
            self.load_deep_zoom_image(images[0])
            return
        choices = [i for i in range(len(images)) if i != self.current_index]
        idx = random.choice(choices)  # nosec B311  # NOSONAR S2245 UI navigation, not security-sensitive
        self.current_index = idx
        self.tile_grid_mode = False
        self.load_deep_zoom_image(images[idx])

    def _save_view_state(self):
        """儲存當前圖片的縮放與位置"""
        images = self.model.images
        if images and 0 <= self.current_index < len(images):
            path = images[self.current_index]
            self._view_memory[path] = {
                "zoom": self.zoom,
                "dx": self.dz_offset_x,
                "dy": self.dz_offset_y,
            }

    def _restore_view_state(self, path: str):
        """恢復上次的縮放與位置"""
        mem = self._view_memory.get(path)
        if mem:
            self.zoom = mem["zoom"]
            self.dz_offset_x = mem["dx"]
            self.dz_offset_y = mem["dy"]
        else:
            self.zoom = 1.0
            self.dz_offset_x = 0
            self.dz_offset_y = 0

    def load_deep_zoom_image(self, path):
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
        if path in self._prefetch_cache:
            dzi = self._prefetch_cache.pop(path)
            self.deep_zoom = dzi
            self.tile_manager = TileManager(dzi)
            if path not in self._view_memory:
                self._fit_to_window()
            self._init_animation(path)
            self._prefetch_neighbors()
            self._update_status_info()
            self._notify_deep_zoom_displayed()
            self.update()
            return

        # ===== 快取未命中 → 背景載入 =====
        if path in self._prefetch_workers:
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
        if cur_path and cur_path not in self._view_memory:
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
        self.update()

    def _notify_deep_zoom_displayed(self) -> None:
        """Push the edited base-level array to the deep-zoom-displayed hook."""
        callback = self.on_deep_zoom_displayed
        if callable(callback) and self.deep_zoom is not None:
            # pylint: disable=not-callable  # guarded by callable() above
            callback(self.deep_zoom.levels[0])

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
    # Prefetch（預載入前後 N 張）
    # ---------------------------
    def _prefetch_neighbors(self):
        """載入當前圖片前後 ±N 張到記憶體快取"""
        images = self.model.images
        if not images:
            return
        needed = self._compute_prefetch_targets(images)
        with QMutexLocker(self._prefetch_mutex):
            self._cancel_outdated_prefetch_workers(needed)
            self._evict_outdated_prefetch_cache(needed)
            self._spawn_prefetch_workers(needed)

    def _compute_prefetch_targets(self, images: list[str]) -> set[str]:
        """Return the set of paths to prefetch around ``current_index``.

        The window is asymmetric when the user has been navigating in
        one direction — biased ahead on forward paging, behind on
        backward — so the cache budget lands on images the user is
        actually about to view. Falls back to symmetric ±_PREFETCH_RANGE
        when navigation looks scattered (jump-around browsing)."""
        self._nav_direction_tracker.record(self.current_index)
        range_ahead, range_behind = range_for_direction(
            self._nav_direction_tracker.direction(),
        )
        indices = compute_prefetch_targets(
            self.current_index, len(images),
            range_ahead=range_ahead, range_behind=range_behind,
        )
        return {images[i] for i in indices}

    def _cancel_outdated_prefetch_workers(self, needed: set[str]) -> None:
        # list() required: we mutate _prefetch_workers in-loop.
        for path in list(self._prefetch_workers):  # noqa: S7504
            if path not in needed:
                self._prefetch_workers.pop(path).abort()

    def _evict_outdated_prefetch_cache(self, needed: set[str]) -> None:
        # list() required: we del from _prefetch_cache in-loop.
        for path in list(self._prefetch_cache):  # noqa: S7504
            if path not in needed:
                del self._prefetch_cache[path]

    def _prefetch_distance_for(self, path: str) -> int:
        """Return |index(path) - current_index| for the priority
        helper. Defaults to a large distance when the path isn't in
        the model — happens during transient races; the queue will
        drop the worker on the next ``_cancel_outdated`` pass."""
        try:
            return abs(self.model.images.index(path) - self.current_index)
        except (ValueError, AttributeError):
            return 99

    def _spawn_prefetch_workers(self, needed: set[str]) -> None:
        from Imervue.image.recipe_store import recipe_store
        for path in needed:
            if path in self._prefetch_cache or path in self._prefetch_workers:
                continue
            worker = LoadDeepZoomWorker(path, recipe=recipe_store.get_for_path(path))
            worker.signals.finished.connect(self._on_prefetch_loaded)
            self._prefetch_workers[path] = worker
            # Distance-aware priority: the next neighbour the user
            # might press lands before the far-out ones, so when the
            # pool drains it pulls the most-likely-needed image
            # first regardless of submit order.
            from Imervue.gpu_image_view.worker_pools import priority_for_distance
            distance = self._prefetch_distance_for(path)
            self.prefetch_pool.start(worker, priority_for_distance(distance))

    def _on_prefetch_loaded(self, dzi, path):
        """預載 worker 完成回調"""
        with QMutexLocker(self._prefetch_mutex):
            self._prefetch_workers.pop(path, None)

        # 如果使用者正在等待這張圖（prefetch worker 被當作主載入用）
        if (self.deep_zoom is None
                and self.model.images
                and self.current_index < len(self.model.images)
                and self.model.images[self.current_index] == path):
            self.deep_zoom = dzi
            self.tile_manager = TileManager(dzi)
            self._prefetch_neighbors()
            self.update()
            return

        # 否則存入預載快取
        with QMutexLocker(self._prefetch_mutex):
            self._prefetch_cache[path] = dzi
            while len(self._prefetch_cache) > _PREFETCH_MAX:
                self._prefetch_cache.popitem(last=False)

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

        self.update()

    # ===========================
    # Event
    # ===========================
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if self.tile_grid_mode:
            # 滾輪 → 上下捲動縮圖列表
            scroll_amount = delta / 2  # angleDelta 通常 ±120，/2 → ±60 px
            self.grid_offset_y += scroll_amount
            self.update()
            return
        if self.deep_zoom:
            self._handle_deep_zoom_wheel(event, delta)

    _ZOOM_MIN = 0.05
    _ZOOM_MAX = 50.0

    def _handle_deep_zoom_wheel(self, event, delta) -> None:
        """Apply a wheel zoom step to the deep-zoom view. Scrolling over the
        minimap zooms into the pointed location; elsewhere the zoom re-anchors
        around the cursor. At the zoom limit, surface a throttled toast."""
        factor = 1.1 if delta > 0 else 0.9
        old_zoom = self.zoom
        new_zoom = stepped_zoom(old_zoom, factor, self._ZOOM_MIN, self._ZOOM_MAX)
        if new_zoom == old_zoom:
            self._notify_zoom_limit_once(new_zoom)
            return
        self.zoom = new_zoom
        pos = event.position()
        rect = self._current_minimap_rect()
        if rect is not None and point_in_rect(pos.x(), pos.y(), rect):
            base = self.deep_zoom.levels[0]
            self.dz_offset_x, self.dz_offset_y = recenter_offsets(
                pos.x(), pos.y(), rect, base.shape[1], base.shape[0],
                self.width(), self.height(), new_zoom,
            )
            self._user_locked_view = True
            self._update_status_info()
            self.update()
        else:
            self._anchor_zoom_about(pos, old_zoom, new_zoom)

    _KEYBOARD_ZOOM_FACTOR = 1.25

    def _zoom_step(self, zoom_in: bool) -> None:
        """Keyboard zoom in/out, anchored on the viewport centre."""
        if not self.deep_zoom:
            return
        from PySide6.QtCore import QPointF
        factor = (self._KEYBOARD_ZOOM_FACTOR if zoom_in
                  else 1 / self._KEYBOARD_ZOOM_FACTOR)
        old_zoom = self.zoom
        new_zoom = stepped_zoom(old_zoom, factor, self._ZOOM_MIN, self._ZOOM_MAX)
        if new_zoom == old_zoom:
            self._notify_zoom_limit_once(new_zoom)
            return
        self.zoom = new_zoom
        center = QPointF(self.width() / 2, self.height() / 2)
        self._anchor_zoom_about(center, old_zoom, new_zoom)

    def _fit_window_with_toast(self) -> None:
        if self.deep_zoom:
            self._fit_to_window()
            self.update()
            self._toast("fit_window", "Fit to Window")

    def _anchor_zoom_about(self, pos, old_zoom: float, new_zoom: float) -> None:
        """Re-anchor the deep-zoom offset so the image point under *pos* stays
        put across a zoom change, then refresh status + repaint."""
        self.dz_offset_x = zoom_about_point(
            self.dz_offset_x, pos.x(), old_zoom, new_zoom,
        )
        self.dz_offset_y = zoom_about_point(
            self.dz_offset_y, pos.y(), old_zoom, new_zoom,
        )
        self._user_locked_view = True
        self._update_status_info()
        self.update()

    def _notify_zoom_limit_once(self, new_zoom: float) -> None:
        """Toast the zoom-limit hint once and rearm 2 s later."""
        if getattr(self, '_zoom_limit_shown', False):
            return
        self._zoom_limit_shown = True
        if hasattr(self.main_window, 'toast'):
            limit = "5000%" if new_zoom >= self._ZOOM_MAX else "5%"
            self.main_window.toast.info(f"Zoom limit: {limit}")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: setattr(self, '_zoom_limit_shown', False))

    def mousePressEvent(self, event):
        self.last_pos = event.position()
        self._cancel_hover_preview()

        # ===== 中鍵拖動 =====
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = True
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
            elif self.deep_zoom and self._begin_minimap_nav(event.position()):
                return
            return

        super().mousePressEvent(event)

    def _begin_minimap_nav(self, pos) -> bool:
        """Start click-to-navigate if *pos* is inside the minimap. Returns
        True when the click was consumed by the minimap."""
        rect = self._current_minimap_rect()
        if rect is None or not point_in_rect(pos.x(), pos.y(), rect):
            return False
        self._minimap_dragging = True
        self._minimap_nav_to(pos)
        return True

    def _minimap_nav_to(self, pos) -> None:
        """Recenter the deep-zoom viewport on the image point under *pos*."""
        rect = self._current_minimap_rect()
        if rect is None:
            return
        base = self.deep_zoom.levels[0]
        self.dz_offset_x, self.dz_offset_y = recenter_offsets(
            pos.x(), pos.y(), rect, base.shape[1], base.shape[0],
            self.width(), self.height(), self.zoom,
        )
        self._user_locked_view = True
        self._update_status_info()
        self.update()

    def mouseDoubleClickEvent(self, event):
        # Deep zoom: double-click toggles fit ↔ 100% centred on the cursor,
        # except inside the minimap (which owns clicks for navigation).
        if (event.button() == Qt.MouseButton.LeftButton
                and self.deep_zoom and not self.tile_grid_mode):
            pos = event.position()
            rect = self._current_minimap_rect()
            if rect is None or not point_in_rect(pos.x(), pos.y(), rect):
                self._toggle_zoom_at(pos)
                return
        super().mouseDoubleClickEvent(event)

    def _toggle_zoom_at(self, pos) -> None:
        """Toggle between fit-to-window and 100%.

        Zooming to 100% anchors on the cursor; returning to fit re-centres the
        image (anchoring on the cursor would leave it off-centre once it's
        small enough to fit).
        """
        fit = self._fit_zoom()
        target = toggle_zoom_target(self.zoom, fit)
        if target == fit:
            self._fit_to_window()
            self.update()
            return
        old_zoom = self.zoom
        self.zoom = target
        self._anchor_zoom_about(pos, old_zoom, target)

    def mouseMoveEvent(self, event):
        self._update_hover_state(event)

        if self.last_pos is None:
            self.last_pos = event.position()
            return

        delta = event.position() - self.last_pos
        self.last_pos = event.position()

        if self._middle_dragging:
            self._handle_middle_drag(delta)
            return

        if self._minimap_dragging:
            self._minimap_nav_to(event.position())
            return

        self._handle_left_drag_select(event)

    def _update_hover_state(self, event) -> None:
        # hover 圖片像素座標（status bar 用）
        if self.deep_zoom and not self.tile_grid_mode:
            mx, my = event.position().x(), event.position().y()
            img_x = int((mx - self.dz_offset_x) / max(self.zoom, 1e-9))
            img_y = int((my - self.dz_offset_y) / max(self.zoom, 1e-9))
            self._hover_image_xy = (img_x, img_y)
            self._update_status_info()
        if self.tile_grid_mode:
            self._update_hover_preview(event)

    def _handle_middle_drag(self, delta) -> None:
        if self.tile_grid_mode:
            self.grid_offset_x += delta.x()
            self.grid_offset_y += delta.y()
        elif self.deep_zoom:
            self.dz_offset_x += delta.x()
            self.dz_offset_y += delta.y()
            self._user_locked_view = True
        self.update()

    def _handle_left_drag_select(self, event) -> None:
        if not (
            self.tile_grid_mode
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_start_pos
        ):
            return

        if not self._drag_selecting and not self._try_begin_drag_select(event):
            return

        self._drag_end_pos = event.position()
        self.update()

    def _try_begin_drag_select(self, event) -> bool:
        """Return True once the drag threshold has been exceeded and a frame-
        selection has started. Returns False while still below threshold or
        when the gesture was consumed by drag-out.
        """
        move_delta = event.position() - self._drag_start_pos
        if move_delta.manhattanLength() < QApplication.startDragDistance():
            return False

        from Imervue.gpu_image_view.actions.drag_out import try_start_drag_out
        if try_start_drag_out(self, self._drag_start_pos):
            self._drag_start_pos = None
            self._drag_end_pos = None
            return False

        self.tile_selection_mode = True
        self._drag_selecting = True
        return True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = False
            return
        if event.button() == Qt.MouseButton.LeftButton and self._minimap_dragging:
            self._minimap_dragging = False
            return
        if (
            self.tile_grid_mode
            and event.button() == Qt.MouseButton.LeftButton
            and self._handle_tile_release(event)
        ):
            return
        super().mouseReleaseEvent(event)

    def _handle_tile_release(self, event) -> bool:
        if self._drag_selecting:
            self._finish_drag_select()
            return True
        mx, my = event.position().x(), event.position().y()
        clicked_tile = self._tile_at(mx, my)
        if not clicked_tile:
            return False
        if not self.tile_selection_mode:
            self._enter_deep_zoom(clicked_tile)
            return True
        self._toggle_tile_selection(clicked_tile)
        return True

    def _finish_drag_select(self) -> None:
        select_tiles_in_rect(self._drag_start_pos, self._drag_end_pos, self)
        self._drag_selecting = False
        self._drag_start_pos = None
        self._drag_end_pos = None
        self.update()

    def _tile_at(self, mx: float, my: float) -> str | None:
        for x0, y0, x1, y1, path in self.tile_rects:
            if x0 <= mx <= x1 and y0 <= my <= y1:
                return path
        return None

    def _enter_deep_zoom(self, path: str) -> None:
        self._saved_tile_state = {
            "grid_offset_x": self.grid_offset_x,
            "grid_offset_y": self.grid_offset_y,
            "tile_scale": self.tile_scale,
        }
        self.tile_grid_mode = False
        if path in self.model.images:
            self.current_index = self.model.images.index(path)
        self.load_deep_zoom_image(path)

    def _toggle_tile_selection(self, path: str) -> None:
        if path in self.selected_tiles:
            self.selected_tiles.remove(path)
        else:
            self.selected_tiles.add(path)
        self.update()

    # F1-F5 → colour labels (red/yellow/green/blue/purple). flag-based.
    _COLOR_LABEL_KEYS = {
        Qt.Key.Key_F1: "red",
        Qt.Key.Key_F2: "yellow",
        Qt.Key.Key_F3: "green",
        Qt.Key.Key_F4: "blue",
        Qt.Key.Key_F5: "purple",
    }

    def _handle_f8(self, modifiers) -> None:
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self._show_debug_hud = not self._show_debug_hud
        else:
            self._show_osd = not self._show_osd
        self.update()

    def _handle_escape(self) -> bool:
        """Returns True if Escape was handled."""
        if hasattr(self, '_slideshow') and self._slideshow and self._slideshow.running:
            stop_slideshow(self)
            return True
        if self.main_window.isFullScreen():
            toggle_fullscreen(self)
            return True
        if self.tile_grid_mode and self.selected_tiles:
            self.tile_selection_mode = False
            self.selected_tiles.clear()
            self.update()
            return True
        if self.deep_zoom or self.active_deep_zoom_worker:
            self._exit_deep_zoom_to_grid()
            return True
        return False

    def _exit_deep_zoom_to_grid(self) -> None:
        self._cancel_deep_zoom_worker()
        self._cancel_all_prefetch()
        # Thumbnail size changed while zoomed in → the cached tiles are the
        # old size, so rebuild the grid at the new size instead of restoring
        # the stale layout (which would mismatch the new cell metrics).
        if self._tile_size_dirty and self.model.images:
            self._tile_size_dirty = False
            self._saved_tile_state = None
            self.clear_tile_grid()
            self.load_tile_grid_async(image_paths=self.model.images)
        else:
            self._clear_deep_zoom()
            self.tile_grid_mode = True
            if self._saved_tile_state:
                self.grid_offset_x = self._saved_tile_state["grid_offset_x"]
                self.grid_offset_y = self._saved_tile_state["grid_offset_y"]
                self.tile_scale = self._saved_tile_state["tile_scale"]
                self._saved_tile_state = None
        # 若使用者偏好清單瀏覽，Esc 後切回 list 而非 tile grid
        if hasattr(self.main_window, "after_deep_zoom_escape"):
            self.main_window.after_deep_zoom_escape()
        self.update()

    def _handle_arrow_keys(self, key, modifiers, shift) -> bool:
        ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
        if ctrl and shift and self._handle_folder_jump(key):
            return True
        if self.tile_grid_mode:
            self._scroll_grid_by_arrow(key, shift)
            return True
        if self.deep_zoom:
            return self._switch_image_by_arrow(key)
        return False

    def _handle_folder_jump(self, key) -> bool:
        """Ctrl+Shift+Left/Right → jump to sibling folder. Returns True on hit."""
        if key == Qt.Key.Key_Right:
            switch_to_next_folder(main_gui=self)
            return True
        if key == Qt.Key.Key_Left:
            switch_to_previous_folder(main_gui=self)
            return True
        return False

    def _scroll_grid_by_arrow(self, key, shift) -> None:
        """Translate arrow keys into tile-grid pan deltas."""
        dpr = self.devicePixelRatio() or 1.0
        step = (self.thumbnail_size or 1024) / dpr
        move_step = int(step / 2) if shift else int(step)
        deltas = {
            Qt.Key.Key_Up: (0, move_step),
            Qt.Key.Key_Down: (0, -move_step),
            Qt.Key.Key_Left: (move_step, 0),
            Qt.Key.Key_Right: (-move_step, 0),
        }
        dx, dy = deltas.get(key, (0, 0))
        self.grid_offset_x += dx
        self.grid_offset_y += dy
        self.update()

    def _switch_image_by_arrow(self, key) -> bool:
        """Left / Right → previous / next image in deep zoom. Returns True on hit."""
        if key == Qt.Key.Key_Right:
            switch_to_next_image(main_gui=self)
            return True
        if key == Qt.Key.Key_Left:
            switch_to_previous_image(main_gui=self)
            return True
        return False

    def keyPressEvent(self, event):
        from Imervue.gui.shortcut_settings_dialog import shortcut_manager

        key = event.key()
        modifiers = event.modifiers()

        if (hasattr(self.main_window, "plugin_manager")
                and self.main_window.plugin_manager.dispatch_key_press(
                    key, modifiers, self)):
            return

        shift = modifiers & Qt.KeyboardModifier.ShiftModifier

        if key == Qt.Key.Key_F8:
            self._handle_f8(modifiers)
            return

        no_ctrl_alt = not (modifiers & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier))
        if key in self._COLOR_LABEL_KEYS and no_ctrl_alt:
            self._apply_color_label(self._COLOR_LABEL_KEYS[key])
            return

        if key == Qt.Key.Key_Escape and self._handle_escape():
            return

        arrow = (Qt.Key.Key_Up, Qt.Key.Key_Down,
                 Qt.Key.Key_Left, Qt.Key.Key_Right)
        if key in arrow and self._handle_arrow_keys(key, modifiers, shift):
            return

        mods_int = modifiers.value if hasattr(modifiers, "value") else int(modifiers)
        action = shortcut_manager.get_action(key, mods_int)
        if action is None:
            return
        self._key_dispatch.dispatch(action, modifiers)

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
            self._handle_gesture_event(ev)
            return True
        return super().event(ev)

    def _handle_gesture_event(self, event) -> None:
        from PySide6.QtWidgets import QPinchGesture, QSwipeGesture

        pinch = event.gesture(Qt.GestureType.PinchGesture)
        if isinstance(pinch, QPinchGesture):
            self._apply_pinch(pinch)

        swipe = event.gesture(Qt.GestureType.SwipeGesture)
        if isinstance(swipe, QSwipeGesture):
            self._apply_swipe(swipe)

    def _apply_pinch(self, pinch) -> None:
        """Two-finger pinch → deep-zoom scale anchored at pinch center."""
        if not self.deep_zoom:
            return
        from PySide6.QtWidgets import QPinchGesture
        change = pinch.changeFlags()
        if not (change & QPinchGesture.ChangeFlag.ScaleFactorChanged):
            return
        scale_factor = pinch.scaleFactor()
        if scale_factor <= 0:
            return
        _ZOOM_MIN, _ZOOM_MAX = 0.05, 50.0
        old_zoom = self.zoom
        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, old_zoom * scale_factor))
        if new_zoom == old_zoom:
            return
        # Anchor to center-of-pinch if Qt reported one, else widget center
        center = pinch.centerPoint()
        cx = center.x() if center is not None else self.width() / 2
        cy = center.y() if center is not None else self.height() / 2
        # QPinchGesture reports global coords — convert to local
        with contextlib.suppress(Exception):
            local = self.mapFromGlobal(center.toPoint())
            cx, cy = local.x(), local.y()
        ratio = new_zoom / old_zoom
        self.zoom = new_zoom
        self.dz_offset_x = cx - (cx - self.dz_offset_x) * ratio
        self.dz_offset_y = cy - (cy - self.dz_offset_y) * ratio
        self._update_status_info()
        self.update()

    def _apply_swipe(self, swipe) -> None:
        """Horizontal swipe → previous / next image in deep zoom."""
        if not self.deep_zoom:
            return
        from PySide6.QtWidgets import QSwipeGesture
        if swipe.state() != Qt.GestureState.GestureFinished:
            return
        direction = swipe.horizontalDirection()
        if direction == QSwipeGesture.SwipeDirection.Left:
            switch_to_next_image(main_gui=self)
        elif direction == QSwipeGesture.SwipeDirection.Right:
            switch_to_previous_image(main_gui=self)

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
        from Imervue.gpu_image_view.images.image_loader import open_path
        from Imervue.user_settings.recent_image import add_recent_folder, add_recent_image
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.menu.recent_menu import rebuild_recent_menu

        urls = event.mimeData().urls()
        if not urls:
            return

        paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if not paths:
            return

        self.clear_tile_grid()
        first = paths[0]
        mw = self.main_window
        lang = mw.language_wrapper.language_word_dict

        if Path(first).is_dir():
            mw.model.setRootPath(first)
            mw.tree.setRootIndex(mw.model.index(first))
            open_path(main_gui=self, path=first)
            mw.filename_label.setText(
                lang.get("main_window_current_folder_format", "Current Folder: {path}")
                .format(path=first)
            )
            if hasattr(mw, "breadcrumb"):
                mw.breadcrumb.set_path(first)
            add_recent_folder(first)
            user_setting_dict["user_last_folder"] = first
            mw.watch_folder(first)
        elif Path(first).is_file():
            folder = str(Path(first).parent)
            mw.model.setRootPath(folder)
            mw.tree.setRootIndex(mw.model.index(folder))
            open_path(main_gui=self, path=first)
            if hasattr(mw, "breadcrumb"):
                mw.breadcrumb.set_path(folder)
            add_recent_image(first)
            user_setting_dict["user_last_folder"] = folder
            mw.watch_folder(folder)

        rebuild_recent_menu(mw)
        event.acceptProposedAction()
