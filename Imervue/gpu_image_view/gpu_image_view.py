from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from Imervue.gpu_image_view.actions.delete import undo_delete
from Imervue.gpu_image_view.actions.keyboard_actions import (
    toggle_fullscreen, trash_current_image, trash_selected_tiles,
    copy_image_to_clipboard, rate_current_image,
    toggle_favorite,
)
from Imervue.gpu_image_view.actions.search_dialog import open_search_dialog
from Imervue.gpu_image_view.actions.slideshow import open_slideshow_dialog, stop_slideshow
from Imervue.gpu_image_view.actions.goto_dialog import open_goto_dialog
from Imervue.gui.annotation_dialog import open_annotation_for_path
from Imervue.gpu_image_view.actions.select import (
    switch_to_next_image, switch_to_previous_image, select_tiles_in_rect,
    switch_to_next_folder, switch_to_previous_folder,
)
from Imervue.gpu_image_view.images.image_loader import LoadDeepZoomWorker
from Imervue.gpu_image_view.images.image_model import ImageModel
from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker
from Imervue.menu.right_click_menu import right_click_context_menu

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

import numpy as np
import os
from collections import OrderedDict
from OpenGL.GL import *
from PySide6.QtCore import QThreadPool, QMutex, QMutexLocker, Qt
from PySide6.QtGui import QUndoStack, QPainter, QColor, QPen, QFont, QPainterPath, QImage
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from pathlib import Path

from Imervue.gpu_image_view.gl_renderer import GLRenderer
from Imervue.image.tile_manager import TileManager
import contextlib

# DeepZoom 預載範圍（±N 張）
_PREFETCH_RANGE = 3
_PREFETCH_MAX = _PREFETCH_RANGE * 2 + 1


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
        self.tile_textures = {}
        self.tile_cache = {}  # path -> img_data

        # ===== DeepZoom =====
        self.zoom = 1.0
        self.dz_offset_x = 0
        self.dz_offset_y = 0
        self.last_pos = None
        self.tile_manager = None
        self.deep_zoom = None
        self._saved_tile_state = None


        # ===== 圖片切換控制 =====
        self.model = ImageModel()
        self.model.images = []  # 所有圖片路徑
        self.current_index = 0
        self.on_filename_changed = None
        self.deep_zoom_tile_size = 512
        self.thumbnail_size = 512
        self._slideshow_opacity = 1.0

        # ===== 篩選前完整圖片列表 =====
        self._unfiltered_images: list[str] = []

        # ===== 縮圖排列密度 =====
        # 0 (compact) / 8 (standard) / 16 (relaxed) — 縮圖間額外 padding 像素
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        self.tile_padding = int(user_setting_dict.get("tile_padding", 8))

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
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(min((os.cpu_count() or 4) * 2, 16))
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

        # ===== GL Renderer =====
        self.renderer = GLRenderer()

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

    def _detect_vram_limit(self) -> None:
        """Query the GL driver for real VRAM and size the tile cache to it.

        * NVIDIA: ``GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX`` (0x9048), KB.
        * AMD:    ``TEXTURE_FREE_MEMORY_ATI`` (0x87FC), KB, 4-int vector (we
          take the first — total free pool).

        Fall back to the conservative 1.5 GB default on Intel / software GL
        or any driver that doesn't expose either extension. The detected
        limit is clamped to ``[256 MB, 8 GB]`` so a bad query can't blow up
        memory or accidentally disable the cache.
        """
        import logging as _logging
        _log = _logging.getLogger("Imervue.vram")

        total_kb = 0
        try:
            # NVX_gpu_memory_info — NVIDIA cards
            val = glGetIntegerv(0x9048)
            if isinstance(val, (list, tuple)) and val:
                total_kb = int(val[0])
            elif val is not None:
                total_kb = int(val)
        except Exception:
            total_kb = 0

        if total_kb <= 0:
            try:
                # ATI_meminfo — AMD cards (returns 4 ints; first is total free)
                val = glGetIntegerv(0x87FC)
                if isinstance(val, (list, tuple)) and val:
                    total_kb = int(val[0])
            except Exception:
                total_kb = 0

        # Clear any GL error left by the probes above — neither extension is
        # guaranteed to exist, and we don't want a GL_INVALID_ENUM lingering
        # into the next real draw call.
        with contextlib.suppress(Exception):
            while glGetError() != GL_NO_ERROR:
                pass

        if total_kb <= 0:
            _log.info(
                f"VRAM detection not supported on this driver, using default "
                f"{self._vram_limit_default // (1024 * 1024)} MB"
            )
            return

        total_bytes = total_kb * 1024
        detected = int(total_bytes * 0.4)
        min_bytes = 256 * 1024 * 1024        # 256 MB floor
        max_bytes = 8 * 1024 * 1024 * 1024   # 8 GB ceiling
        detected = max(min_bytes, min(max_bytes, detected))
        self._vram_limit = detected
        _log.info(
            f"Detected VRAM {total_bytes // (1024 * 1024)} MB → tile cache "
            f"limit set to {detected // (1024 * 1024)} MB"
        )

    def resizeGL(self, w, h):
        dpr = self.devicePixelRatio()
        glViewport(0, 0, int(w * dpr), int(h * dpr))
        if self.renderer.use_shaders:
            self.renderer.set_ortho(w, h)
        else:
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            glOrtho(0, w, h, 0, -1, 1)
            glMatrixMode(GL_MODELVIEW)

    # ===========================
    # 繪製
    # ===========================
    def paintGL(self):
        painter = QPainter(self)
        painter.beginNativePainting()

        glClear(GL_COLOR_BUFFER_BIT)

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
    def paint_tile_grid(self):

        glLoadIdentity()

        # 預先淘汰超出 VRAM 上限的紋理（不在逐 tile 迴圈中做）
        self._evict_tile_textures_if_needed()

        images = self.model.images
        if self.thumbnail_size is not None:
            base_tile = self.thumbnail_size
        elif self.tile_cache:
            # 用第一張圖實際寬度當排版基準
            first_img = next(iter(self.tile_cache.values()))
            base_tile = first_img.shape[1]
        else:
            base_tile = 256

        scaled_tile = base_tile * self.tile_scale
        pad = self.tile_padding
        cell = scaled_tile + pad
        cols = max(1, int(self.width() // cell))
        self.tile_rects = []
        # Placeholders for tiles whose thumbnail hasn't arrived yet — rendered
        # as dark squares so the grid layout is visible immediately. Stored
        # in screen coords; consumed by ``_draw_tile_placeholders`` overlay.
        self.placeholder_rects: list[tuple[float, float, float, float]] = []

        # 在迴圈外設定一次 GL 狀態，避免每張 tile 都重複呼叫
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        vw, vh = self.width(), self.height()

        for i, path in enumerate(images):

            # 沒載入完成 → 畫預留格子佔位
            if path not in self.tile_cache:
                row = i // cols
                col = i % cols
                x0 = col * cell + self.grid_offset_x
                y0 = row * cell + self.grid_offset_y
                x1 = x0 + scaled_tile
                y1 = y0 + scaled_tile
                if x1 >= 0 and x0 <= vw and y1 >= 0 and y0 <= vh:
                    # Dark placeholder via renderer (kept visually subtle)
                    self.renderer.draw_colored_rect(
                        x0, y0, x1, y1, 0.14, 0.14, 0.14, 1.0, filled=True
                    )
                    self.renderer.draw_colored_rect(
                        x0, y0, x1, y1, 0.28, 0.28, 0.28, 1.0, filled=False
                    )
                    self.placeholder_rects.append((x0, y0, x1, y1))
                continue

            img_data = self.tile_cache[path]

            row = i // cols
            col = i % cols

            x0 = col * cell + self.grid_offset_x
            y0 = row * cell + self.grid_offset_y
            x1 = x0 + img_data.shape[1] * self.tile_scale
            y1 = y0 + img_data.shape[0] * self.tile_scale

            # Viewport 裁切
            if x1 < 0 or x0 > vw or y1 < 0 or y0 > vh:
                continue

            self.tile_rects.append((x0, y0, x1, y1, path))

            # ===== GPU texture =====
            if path not in self.tile_textures:
                tex_bytes = img_data.shape[1] * img_data.shape[0] * 4
                if self._vram_usage + tex_bytes > self._vram_limit:
                    continue  # 已在 evict 階段清理過，仍超出則跳過

                tex = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, tex)

                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                             img_data.shape[1], img_data.shape[0], 0,
                             GL_RGBA, GL_UNSIGNED_BYTE, img_data)

                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

                self.tile_textures[path] = tex
                self._tile_tex_sizes[path] = tex_bytes
                self._vram_usage += tex_bytes

            self.renderer.draw_textured_quad(x0, y0, x1, y1, self.tile_textures[path])

        # Tile grid border
        if self.tile_rects:
            glDisable(GL_TEXTURE_2D)
            glLineWidth(1)
            for x0, y0, x1, y1, _path in self.tile_rects:
                self.renderer.draw_colored_rect(x0, y0, x1, y1, 0.3, 0.3, 0.3, 1.0, filled=False)
            glEnable(GL_TEXTURE_2D)

        # Tile selection overlay
        if self.tile_selection_mode:
            glDisable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glLineWidth(4)

            for x0, y0, x1, y1, path in self.tile_rects:
                if path in self.selected_tiles:
                    # 藍色粗邊框
                    glColor4f(0.18, 0.5, 1.0, 1.0)
                    glBegin(GL_LINE_LOOP)
                    glVertex2f(x0, y0)
                    glVertex2f(x1, y0)
                    glVertex2f(x1, y1)
                    glVertex2f(x0, y1)
                    glEnd()

                    # 右上藍色圓 + 勾
                    circle_radius = 9
                    cx = x1 - 12
                    cy = y0 + 12
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

            glDisable(GL_BLEND)
            glEnable(GL_TEXTURE_2D)
            glColor4f(1, 1, 1, 1)
            glLineWidth(1)

        if self._drag_selecting and self._drag_start_pos and self._drag_end_pos:
            x0, y0 = self._drag_start_pos.x(), self._drag_start_pos.y()
            x1, y1 = self._drag_end_pos.x(), self._drag_end_pos.y()

            left = min(x0, x1)
            right = max(x0, x1)
            top = min(y0, y1)
            bottom = max(y0, y1)

            # ===== 明確設定狀態（不要 push/pop）=====
            glDisable(GL_TEXTURE_2D)

            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            # 淡藍填充
            glColor4f(0.18, 0.5, 1.0, 0.08)
            glBegin(GL_QUADS)
            glVertex2f(left, top)
            glVertex2f(right, top)
            glVertex2f(right, bottom)
            glVertex2f(left, bottom)
            glEnd()

            # 藍色粗框
            glColor4f(0.18, 0.5, 1.0, 1.0)
            glLineWidth(3)
            glBegin(GL_LINE_LOOP)
            glVertex2f(left, top)
            glVertex2f(right, top)
            glVertex2f(right, bottom)
            glVertex2f(left, bottom)
            glEnd()

            # ===== 恢復狀態 =====
            glDisable(GL_BLEND)
            glEnable(GL_TEXTURE_2D)
            glColor4f(1, 1, 1, 1)

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

        if self.renderer.use_shaders:
            # 建立 scale+translate MVP
            import numpy as _np
            mvp = _np.eye(4, dtype=_np.float32)
            from Imervue.gpu_image_view.gl_renderer import _ortho
            base_ortho = _ortho(0, self.width(), self.height(), 0, -1, 1)
            # 先 translate 再 scale
            trans = _np.eye(4, dtype=_np.float32)
            trans[3, 0] = self.dz_offset_x / scale_x
            trans[3, 1] = self.dz_offset_y / scale_y
            scl = _np.eye(4, dtype=_np.float32)
            scl[0, 0] = scale_x
            scl[1, 1] = scale_y
            mvp = trans @ scl @ base_ortho
            self.renderer.set_mvp(mvp)
        else:
            glLoadIdentity()
            glScalef(scale_x, scale_y, 1)
            glTranslatef(self.dz_offset_x / scale_x, self.dz_offset_y / scale_y, 0)

        # 計算 viewport 內 tiles
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
                if 0 <= tx * tile_size < w and 0 <= ty * tile_size < h:
                    tex = self.tile_manager.get_tile(level, tx, ty, tile_size)
                    if tex is None:
                        continue
                    tile_w = min(tile_size, w - tx * tile_size)
                    tile_h = min(tile_size, h - ty * tile_size)
                    x = tx * tile_size
                    y = ty * tile_size
                    self.renderer.draw_textured_quad(x, y, x + tile_w, y + tile_h, tex,
                                                      self._slideshow_opacity)

        # 恢復 ortho MVP for other rendering
        if self.renderer.use_shaders:
            self.renderer.set_ortho(self.width(), self.height())

    # ---------------------------
    # 小地圖（Deep Zoom）
    # ---------------------------
    _MINIMAP_MAX_W = 180
    _MINIMAP_MARGIN = 12
    _MINIMAP_OPACITY = 0.85

    def _paint_minimap(self):
        if not self.deep_zoom:
            return

        base = self.deep_zoom.levels[0]
        img_w, img_h = base.shape[1], base.shape[0]

        # 小地圖尺寸（等比縮放）
        aspect = img_w / max(img_h, 1)
        mm_w = self._MINIMAP_MAX_W
        mm_h = int(mm_w / max(aspect, 0.1))
        if mm_h > 140:
            mm_h = 140
            mm_w = int(mm_h * aspect)
        margin = self._MINIMAP_MARGIN

        # 小地圖左上角在畫面座標
        mm_x = self.width() - mm_w - margin
        mm_y = self.height() - mm_h - margin

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
            self._minimap_tex = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self._minimap_tex)
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
            td = thumb
            if td.shape[2] == 3:
                alpha = np.full((*td.shape[:2], 1), 255, dtype=np.uint8)
                td = np.concatenate([td, alpha], axis=2)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                         td.shape[1], td.shape[0], 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, td.astype(np.uint8))
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
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
    # QPainter 覆蓋層
    # ---------------------------
    def _paint_overlay(self, painter: QPainter):
        need_labels = self.tile_grid_mode and self.tile_rects
        need_zoom = (not self.tile_grid_mode) and self.deep_zoom
        need_hist = need_zoom and self._show_histogram
        need_anim = self._animation and self._animation.is_animated
        need_osd = need_zoom and self._show_osd
        need_hud = self._show_debug_hud
        need_pixel = need_zoom and self._pixel_view and self.zoom >= 4.0
        if not (need_labels or need_zoom or need_hist or need_anim
                or need_osd or need_hud or need_pixel):
            return

        # 在獨立 QImage 上以裝置解析度繪製，避免 QOpenGLWidget FBO 模糊
        dpr = self.devicePixelRatio()
        w, h = self.width(), self.height()
        img = QImage(int(w * dpr), int(h * dpr), QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.GlobalColor.transparent)

        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if need_labels:
            self._draw_tile_labels(p)
            self._draw_tile_badges(p)
            self._draw_tile_placeholders(p)
        if need_zoom:
            self._draw_zoom_indicator(p)
        if need_hist:
            self._draw_histogram(p)
        if need_anim:
            self._draw_anim_indicator(p)
        if need_osd:
            self._draw_osd(p)
        if need_hud:
            self._draw_debug_hud(p)
        if need_pixel:
            self._draw_pixel_view(p)

        p.end()
        painter.drawImage(0, 0, img)

    def _draw_tile_labels(self, painter: QPainter):
        """在每個縮圖下方繪製檔名"""
        font = QFont("Segoe UI")
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()

        for x0, _y0, x1, y1, path in self.tile_rects:
            name = Path(path).stem
            tw = x1 - x0
            elided = fm.elidedText(name, Qt.TextElideMode.ElideRight, int(tw))
            tx = int(x0 + (tw - fm.horizontalAdvance(elided)) / 2)
            ty = int(y1 + fm.ascent() + 2)
            if ty < self.height() + fm.height():
                # 陰影
                painter.setPen(QColor(0, 0, 0, 180))
                painter.drawText(tx + 1, ty + 1, elided)
                # 文字
                painter.setPen(QColor(220, 220, 220))
                painter.drawText(tx, ty, elided)

    def _draw_tile_badges(self, painter: QPainter):
        """在每個縮圖角落繪製評分/收藏/書籤/色彩標籤徽章."""
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.user_settings.bookmark import is_bookmarked
        from Imervue.user_settings.color_labels import COLOR_RGB, _store as _color_store

        ratings = user_setting_dict.get("image_ratings", {}) or {}
        favs = user_setting_dict.get("image_favorites", set())
        if not isinstance(favs, set):
            # settings may have been serialized as list
            try:
                favs = set(favs)
            except TypeError:
                favs = set()
        color_store = _color_store()

        font = QFont("Segoe UI")
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)

        for x0, y0, x1, y1, path in self.tile_rects:
            # Left edge: colour label strip (6 px wide)
            color_name = color_store.get(path)
            if color_name and color_name in COLOR_RGB:
                r, g, b = COLOR_RGB[color_name]
                painter.fillRect(
                    int(x0), int(y0), 6, int(y1 - y0),
                    QColor(r, g, b, 230),
                )

            # Top-left: favorite heart — nudged right to dodge the colour strip
            if path in favs:
                offset = 10 if color_name else 4
                painter.fillRect(int(x0 + offset), int(y0 + 4), 18, 18,
                                 QColor(0, 0, 0, 140))
                painter.setPen(QColor(255, 90, 120))
                painter.drawText(int(x0 + offset + 2), int(y0 + 18), "\u2665")

            # Top-right: bookmark
            if is_bookmarked(path):
                painter.fillRect(int(x1 - 22), int(y0 + 4), 18, 18,
                                 QColor(0, 0, 0, 140))
                painter.setPen(QColor(255, 210, 80))
                painter.drawText(int(x1 - 20), int(y0 + 18), "\u2605")

            # Bottom-left: star rating
            rating = ratings.get(path, 0)
            if rating and rating > 0:
                badge_text = "\u2605" * int(rating)
                fm = painter.fontMetrics()
                tw = fm.horizontalAdvance(badge_text)
                painter.fillRect(int(x0 + 4), int(y1 - 20), tw + 8, 18,
                                 QColor(0, 0, 0, 140))
                painter.setPen(QColor(255, 210, 80))
                painter.drawText(int(x0 + 8), int(y1 - 6), badge_text)

    def _draw_tile_placeholders(self, painter: QPainter):
        """Draw a subtle spinner-like dot pattern on unloaded tile slots.

        The dots rotate via the animation frame counter so the user sees
        activity while thumbnails stream in, reinforcing that something is
        happening beyond the bottom progress bar.
        """
        rects = getattr(self, "placeholder_rects", None)
        if not rects:
            return

        import time
        phase = (time.monotonic() % 1.0) * 2 * 3.14159
        painter.setPen(QColor(140, 140, 140, 200))
        font = QFont("Segoe UI")
        font.setPixelSize(11)
        painter.setFont(font)

        for x0, y0, x1, y1 in rects:
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            # Four dots spinning around centre; size proportional to tile
            radius = min(x1 - x0, y1 - y0) * 0.12
            for i in range(4):
                angle = phase + i * (3.14159 / 2)
                dot_x = cx + radius * 1.6 * np.cos(angle)
                dot_y = cy + radius * 1.6 * np.sin(angle)
                alpha = 80 + int(120 * (i / 3))
                painter.setBrush(QColor(200, 200, 200, alpha))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    int(dot_x - radius / 3), int(dot_y - radius / 3),
                    int(radius * 2 / 3), int(radius * 2 / 3),
                )

        # Trigger another paint on next frame while placeholders exist — cheap
        # because only the overlay layer is repainted.
        if not getattr(self, "_placeholder_timer", None):
            from PySide6.QtCore import QTimer
            t = QTimer(self)
            t.setInterval(80)
            t.timeout.connect(self._tick_placeholder)
            self._placeholder_timer = t
        if not self._placeholder_timer.isActive():
            self._placeholder_timer.start()

    def _tick_placeholder(self) -> None:
        if self.tile_grid_mode and getattr(self, "placeholder_rects", None):
            self.update()
        else:
            # No placeholders left — stop the spinner timer
            timer = getattr(self, "_placeholder_timer", None)
            if timer and timer.isActive():
                timer.stop()

    def _draw_zoom_indicator(self, painter: QPainter):
        """在右下角小地圖上方顯示縮放百分比"""
        pct = f"{self.zoom * 100:.0f}%"
        font = QFont("Consolas")
        font.setPixelSize(15)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(pct)
        x = self.width() - tw - self._MINIMAP_MARGIN - 2
        y = self.height() - self._MINIMAP_MARGIN - 8
        # 小地圖高度估算
        if self.deep_zoom:
            base = self.deep_zoom.levels[0]
            aspect = base.shape[1] / max(base.shape[0], 1)
            mm_h = int(self._MINIMAP_MAX_W / max(aspect, 0.1))
            mm_h = min(mm_h, 140)
            y = self.height() - self._MINIMAP_MARGIN - mm_h - fm.height() - 4

        painter.setPen(QColor(0, 0, 0, 160))
        painter.drawText(x + 1, y + 1, pct)
        painter.setPen(QColor(230, 230, 230))
        painter.drawText(x, y, pct)

    def _draw_histogram(self, painter: QPainter):
        """繪製 RGB 直方圖覆蓋層"""
        if not self.deep_zoom:
            return

        # 取得/快取直方圖資料
        images = self.model.images
        if not images or self.current_index >= len(images):
            return
        cur_path = images[self.current_index]
        if cur_path and (not self._histogram_cache or self._histogram_cache[0] != cur_path):
            img = self.deep_zoom.levels[-1]  # 用最低解析度計算
            self._histogram_cache = (
                cur_path,
                np.histogram(img[:, :, 0], bins=256, range=(0, 256))[0],
                np.histogram(img[:, :, 1], bins=256, range=(0, 256))[0],
                np.histogram(img[:, :, 2], bins=256, range=(0, 256))[0],
            )

        if not self._histogram_cache:
            return

        _, hr, hg, hb = self._histogram_cache
        h_max = max(hr.max(), hg.max(), hb.max(), 1)

        # 繪製區域：左上角
        hx, hy, hw, hh = 12, 12, 256, 120

        # 半透明背景
        painter.fillRect(hx - 2, hy - 2, hw + 4, hh + 4, QColor(0, 0, 0, 140))

        for hist, color in [(hr, QColor(220, 60, 60, 120)),
                            (hg, QColor(60, 200, 60, 120)),
                            (hb, QColor(60, 100, 220, 120))]:
            path = QPainterPath()
            path.moveTo(hx, hy + hh)
            for i in range(256):
                bh = hist[i] / h_max * hh
                path.lineTo(hx + i, hy + hh - bh)
            path.lineTo(hx + 255, hy + hh)
            path.closeSubpath()
            painter.fillPath(path, color)

    def _draw_anim_indicator(self, painter: QPainter):
        """繪製動畫幀指示器（底部中央）"""
        anim = self._animation
        if not anim or not anim.is_animated:
            return

        lang = self.main_window.language_wrapper.language_word_dict

        frame_text = lang.get("anim_frame_indicator", "Frame {current}/{total}").format(
            current=anim.current_frame + 1, total=anim.total_frames
        )
        status = (
            lang.get("anim_play", "Play") if not anim.playing
            else lang.get("anim_pause", "Pause")
        )
        speed_text = lang.get("anim_speed", "Speed: {speed}x").format(speed=f"{anim.speed:.1f}")
        text = f"{status}  |  {frame_text}  |  {speed_text}"

        font = QFont("Consolas")
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        x = (self.width() - tw) // 2
        y = self.height() - 20

        # 背景
        painter.fillRect(x - 8, y - th - 2, tw + 16, th + 8, QColor(0, 0, 0, 160))
        # 文字
        painter.setPen(QColor(230, 230, 230))
        painter.drawText(x, y, text)

    # ---------------------------
    # OSD + Debug HUD
    # ---------------------------
    def _current_path(self) -> str | None:
        imgs = self.model.images
        if imgs and 0 <= self.current_index < len(imgs):
            return imgs[self.current_index]
        return None

    def _draw_osd(self, painter: QPainter):
        """F3 OSD — 右上角顯示檔名 / 尺寸 / 格式 / 檔案大小."""
        path = self._current_path()
        if not path or not self.deep_zoom:
            return

        base = self.deep_zoom.levels[0]
        h, w = base.shape[:2]

        try:
            size_bytes = os.path.getsize(path)
            if size_bytes >= 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{size_bytes / 1024:.1f} KB"
        except OSError:
            size_str = "—"

        lines = [
            Path(path).name,
            f"{w} × {h}",
            f"{Path(path).suffix.lstrip('.').upper() or '—'}   {size_str}",
        ]

        font = QFont("Segoe UI")
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()

        pad_x, pad_y = 10, 6
        line_h = fm.height()
        box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2

        # 右上角，避開 histogram(左上) 與 minimap(右下)
        x = self.width() - box_w - 12
        y = 12

        painter.fillRect(x, y, box_w, box_h, QColor(0, 0, 0, 170))
        painter.setPen(QColor(230, 230, 230))
        for i, line in enumerate(lines):
            painter.drawText(x + pad_x, y + pad_y + fm.ascent() + i * line_h, line)

    def _draw_debug_hud(self, painter: QPainter):
        """Ctrl+F3 Debug HUD — 顯示 VRAM / cache / 執行緒池."""
        vram_mb = self._vram_usage / (1024 * 1024)
        limit_mb = self._vram_limit / (1024 * 1024)
        pct = (self._vram_usage / self._vram_limit * 100) if self._vram_limit else 0
        tile_count = len(self.tile_textures)
        cache_count = len(self.tile_cache)
        prefetch_count = len(self._prefetch_cache)
        active_threads = self.thread_pool.activeThreadCount()
        max_threads = self.thread_pool.maxThreadCount()

        lines = [
            f"VRAM  {vram_mb:6.1f} / {limit_mb:6.1f} MB  ({pct:4.1f}%)",
            f"Tile tex   {tile_count:4d}   cache {cache_count:4d}",
            f"Prefetch   {prefetch_count:4d}   workers {len(self._prefetch_workers)}",
            f"Threads    {active_threads:4d} / {max_threads}",
            f"Gen {self._load_generation}   Zoom {self.zoom * 100:.1f}%",
        ]

        font = QFont("Consolas")
        font.setPixelSize(12)
        painter.setFont(font)
        fm = painter.fontMetrics()

        pad_x, pad_y = 8, 5
        line_h = fm.height()
        box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2

        # 左下角 — 不擋直方圖 / minimap / OSD
        x = 12
        y = self.height() - box_h - 12

        painter.fillRect(x, y, box_w, box_h, QColor(0, 0, 0, 180))
        painter.setPen(QColor(120, 220, 120))
        for i, line in enumerate(lines):
            painter.drawText(x + pad_x, y + pad_y + fm.ascent() + i * line_h, line)

    def _draw_pixel_view(self, painter: QPainter):
        """Shift+P — 在 zoom ≥ 4x 時繪製像素網格 + hover pixel RGB.

        Only active when the per-pixel square is big enough (>= 4 screen
        pixels) so the grid doesn't drown in moiré. Hovered pixel value is
        shown in a small HUD near the cursor.
        """
        if not self.deep_zoom or self.zoom < 4.0:
            return

        base = self.deep_zoom.levels[0]
        h, w = base.shape[:2]

        # Viewport 在原圖座標
        left = -self.dz_offset_x / self.zoom
        top = -self.dz_offset_y / self.zoom
        right = left + self.width() / self.zoom
        bottom = top + self.height() / self.zoom

        x0 = max(0, int(left))
        y0 = max(0, int(top))
        x1 = min(w, int(right) + 1)
        y1 = min(h, int(bottom) + 1)

        # 整張圖 zoom 很大時，格子線反而會變太密；限制繪製格子數量
        if (x1 - x0) * (y1 - y0) > 40000:
            pass  # 只畫 hover 的 RGB，不畫整張網格
        else:
            pen = QPen(QColor(128, 128, 128, 120))
            pen.setWidth(0)
            painter.setPen(pen)
            # 垂直線
            for gx in range(x0, x1 + 1):
                sx = gx * self.zoom + self.dz_offset_x
                painter.drawLine(int(sx), int(y0 * self.zoom + self.dz_offset_y),
                                 int(sx), int(y1 * self.zoom + self.dz_offset_y))
            # 水平線
            for gy in range(y0, y1 + 1):
                sy = gy * self.zoom + self.dz_offset_y
                painter.drawLine(int(x0 * self.zoom + self.dz_offset_x), int(sy),
                                 int(x1 * self.zoom + self.dz_offset_x), int(sy))

        # Hover pixel HUD
        if self._hover_image_xy is not None:
            cx, cy = self._hover_image_xy
            if 0 <= cx < w and 0 <= cy < h:
                pixel = base[cy, cx]
                r = int(pixel[0])
                g = int(pixel[1])
                b = int(pixel[2])
                a = int(pixel[3]) if base.shape[2] >= 4 else 255
                hex_str = f"#{r:02X}{g:02X}{b:02X}"

                font = QFont("Consolas")
                font.setPixelSize(12)
                painter.setFont(font)
                fm = painter.fontMetrics()

                lines = [
                    f"({cx}, {cy})",
                    f"RGB {r:3d} {g:3d} {b:3d}",
                    f"A   {a:3d}    {hex_str}",
                ]
                pad_x, pad_y = 6, 4
                line_h = fm.height()
                box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
                box_h = line_h * len(lines) + pad_y * 2

                # Highlight the target pixel square
                sx = cx * self.zoom + self.dz_offset_x
                sy = cy * self.zoom + self.dz_offset_y
                size = self.zoom
                pen = QPen(QColor(255, 220, 0, 230))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(int(sx), int(sy), int(size), int(size))

                # Place HUD offset from cursor, clamped to viewport
                hx = int(sx) + int(size) + 12
                hy = int(sy)
                if hx + box_w > self.width():
                    hx = int(sx) - box_w - 12
                if hy + box_h > self.height():
                    hy = self.height() - box_h - 4
                hy = max(hy, 0)

                painter.fillRect(hx, hy, box_w, box_h, QColor(0, 0, 0, 190))
                painter.setPen(QColor(240, 240, 240))
                for i, line in enumerate(lines):
                    painter.drawText(hx + pad_x, hy + pad_y + fm.ascent() + i * line_h, line)

                # Colour swatch
                painter.fillRect(
                    hx + box_w - 20, hy + pad_y, 14, 14, QColor(r, g, b)
                )

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
            # Tile grid / no image — only index text is meaningful
            if images:
                mw.update_status_info(
                    index=f"{idx + 1 if self.deep_zoom else len(images)}/{len(images)}"
                    if self.deep_zoom else f"— / {len(images)}",
                    resolution="", size="", zoom="", cursor="",
                )
            else:
                mw.clear_status_info()
            return

        path = images[idx]
        base = self.deep_zoom.levels[0]
        h, w = base.shape[:2]

        try:
            size_bytes = os.path.getsize(path)
            if size_bytes >= 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{size_bytes / 1024:.1f} KB"
        except OSError:
            size_str = ""

        cursor_str = ""
        if self._hover_image_xy is not None:
            cx, cy = self._hover_image_xy
            if 0 <= cx < w and 0 <= cy < h:
                cursor_str = f"x={cx}, y={cy}"

        from Imervue.user_settings.color_labels import get_color_label
        color_label = get_color_label(path) or ""

        mw.update_status_info(
            index=f"{idx + 1}/{len(images)}",
            resolution=f"{w}×{h}",
            size=size_str,
            zoom=f"{self.zoom * 100:.0f}%",
            cursor=cursor_str,
            label=color_label,
        )

    # ---------------------------
    # Fit to Window
    # ---------------------------
    def _fit_to_window(self):
        """自動縮放使圖片完整顯示在視窗內"""
        if not self.deep_zoom:
            return
        base = self.deep_zoom.levels[0]
        img_w, img_h = base.shape[1], base.shape[0]
        w, h = self.width() or 1, self.height() or 1
        self.zoom = min(w / img_w, h / img_h, 1.0)
        displayed_w = img_w * self.zoom
        displayed_h = img_h * self.zoom
        self.dz_offset_x = (w - displayed_w) / 2
        self.dz_offset_y = (h - displayed_h) / 2

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
            # 嘗試從剪貼簿取得檔案路徑
            mime = clipboard.mimeData()
            if mime and mime.hasUrls():
                for url in mime.urls():
                    p = url.toLocalFile()
                    if p and Path(p).is_file():
                        from Imervue.gpu_image_view.images.image_loader import open_path
                        open_path(main_gui=self, path=p)
                        return
            return

        # 將剪貼簿圖片存檔到目前資料夾
        images = self.model.images
        if images:
            folder = str(Path(images[0]).parent)
        else:
            from Imervue.user_settings.user_setting_dict import user_setting_dict
            folder = user_setting_dict.get("user_last_folder", "")
        if not folder or not Path(folder).is_dir():
            return

        # 產生唯一檔名
        import time
        name = f"pasted_{int(time.time())}.png"
        save_path = str(Path(folder) / name)
        qimg.save(save_path, "PNG")

        # 加入 model 並載入
        if save_path not in images:
            images.append(save_path)
            images.sort(key=lambda p: os.path.basename(p).lower())

        from Imervue.gpu_image_view.images.image_loader import open_path
        open_path(main_gui=self, path=save_path)

        if hasattr(self.main_window, 'toast'):
            self.main_window.toast.info(f"Pasted: {name}")

    # ===========================
    # 載入管理
    # ===========================
    def _evict_tile_textures_if_needed(self):
        """VRAM 超出上限時淘汰不在視窗內的紋理（在 paint 前呼叫）"""
        if self._vram_usage <= self._vram_limit:
            return
        # 收集目前可見的 path
        visible = set()
        images = self.model.images
        if images and self.thumbnail_size is not None:
            base_tile = self.thumbnail_size
        elif self.tile_cache:
            first_img = next(iter(self.tile_cache.values()))
            base_tile = first_img.shape[1]
        else:
            base_tile = 256
        scaled_tile = base_tile * self.tile_scale
        pad = self.tile_padding
        cell = scaled_tile + pad
        cols = max(1, int(self.width() // cell))
        for i, p in enumerate(images):
            if p not in self.tile_cache:
                continue
            row = i // cols
            col = i % cols
            x0 = col * cell + self.grid_offset_x
            y0 = row * cell + self.grid_offset_y
            img = self.tile_cache[p]
            x1 = x0 + img.shape[1] * self.tile_scale
            y1 = y0 + img.shape[0] * self.tile_scale
            if x1 >= 0 and x0 <= self.width() and y1 >= 0 and y0 <= self.height():
                visible.add(p)
        # 淘汰不可見的紋理
        for p in list(self.tile_textures):
            if self._vram_usage <= self._vram_limit:
                break
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

    # ---------------------------
    # Tile Grid 載入
    # ---------------------------
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

        for path in image_paths:
            worker = LoadThumbnailWorker(path, self.thumbnail_size, gen)
            worker.signals.finished.connect(self._on_thumbnail_loaded)
            self.active_tile_workers.append(worker)
            self.thread_pool.start(worker)

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

        # 更新進度
        self._tile_load_count = len(self.tile_cache)
        if hasattr(self.main_window, 'show_progress'):
            self.main_window.show_progress(self._tile_load_count, self._tile_load_total)

        self.update()

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

        targets: list[str] = []
        if self.tile_grid_mode and self.tile_selection_mode and self.selected_tiles:
            targets = list(self.selected_tiles)
        elif self.deep_zoom:
            images = self.model.images
            if images and 0 <= self.current_index < len(images):
                targets = [images[self.current_index]]
        elif self.tile_grid_mode and self._hover_last_path:
            targets = [self._hover_last_path]

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
        """Jump to a random image in the current list, avoiding re-pick if possible."""
        import random
        images = self.model.images
        if not images:
            return
        if len(images) == 1:
            self.current_index = 0
            self.load_deep_zoom_image(images[0])
            return
        choices = [i for i in range(len(images)) if i != self.current_index]
        idx = random.choice(choices)
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
        self.thread_pool.start(worker)

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
        cur_path = self.model.images[self.current_index] if self.model.images else None
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
        self.update()

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

        # 計算需要預載的路徑集合
        needed: set[str] = set()
        for offset in range(-_PREFETCH_RANGE, _PREFETCH_RANGE + 1):
            if offset == 0:
                continue
            idx = self.current_index + offset
            if 0 <= idx < len(images):
                needed.add(images[idx])

        with QMutexLocker(self._prefetch_mutex):
            # 取消不再需要的 worker
            for path in list(self._prefetch_workers):
                if path not in needed:
                    self._prefetch_workers.pop(path).abort()

            # 淘汰不在範圍內的快取
            for path in list(self._prefetch_cache):
                if path not in needed:
                    del self._prefetch_cache[path]

            # 對需要且尚未載入/正在載入的路徑啟動 worker
            from Imervue.image.recipe_store import recipe_store
            for path in needed:
                if path in self._prefetch_cache or path in self._prefetch_workers:
                    continue
                worker = LoadDeepZoomWorker(path, recipe=recipe_store.get_for_path(path))
                worker.signals.finished.connect(self._on_prefetch_loaded)
                self._prefetch_workers[path] = worker
                self.thread_pool.start(worker)

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

        elif self.deep_zoom:
            _ZOOM_MIN, _ZOOM_MAX = 0.05, 50.0
            factor = 1.1 if delta > 0 else 0.9
            old_zoom = self.zoom
            new_zoom = old_zoom * factor
            new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, new_zoom))
            if new_zoom == old_zoom:
                # 已達縮放極限，顯示提示（節流：不重複觸發）
                if not getattr(self, '_zoom_limit_shown', False):
                    self._zoom_limit_shown = True
                    if hasattr(self.main_window, 'toast'):
                        limit = "5000%" if new_zoom >= _ZOOM_MAX else "5%"
                        self.main_window.toast.info(f"Zoom limit: {limit}")
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(2000, lambda: setattr(self, '_zoom_limit_shown', False))
                return
            self.zoom = new_zoom

            # 以滑鼠游標為中心縮放
            mx = event.position().x()
            my = event.position().y()
            ratio = self.zoom / old_zoom
            self.dz_offset_x = mx - (mx - self.dz_offset_x) * ratio
            self.dz_offset_y = my - (my - self.dz_offset_y) * ratio

            self._update_status_info()
            self.update()

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
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # ===== 更新 hover 圖片像素座標（status bar 用）=====
        if self.deep_zoom and not self.tile_grid_mode:
            mx, my = event.position().x(), event.position().y()
            img_x = int((mx - self.dz_offset_x) / max(self.zoom, 1e-9))
            img_y = int((my - self.dz_offset_y) / max(self.zoom, 1e-9))
            self._hover_image_xy = (img_x, img_y)
            self._update_status_info()

        # ===== Hover preview (tile grid only) =====
        if self.tile_grid_mode:
            self._update_hover_preview(event)

        if self.last_pos is None:
            self.last_pos = event.position()
            return

        delta = event.position() - self.last_pos
        self.last_pos = event.position()

        # ===== 中鍵拖動 =====
        if self._middle_dragging:
            if self.tile_grid_mode:
                self.grid_offset_x += delta.x()
                self.grid_offset_y += delta.y()
            elif self.deep_zoom:
                self.dz_offset_x += delta.x()
                self.dz_offset_y += delta.y()

            self.update()
            return

        # ===== 左鍵拖曳框選 =====
        if (
            self.tile_grid_mode
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_start_pos
        ):
            move_delta = event.position() - self._drag_start_pos
            threshold = QApplication.startDragDistance()

            # 還沒超過系統拖曳門檻
            if not self._drag_selecting:
                if move_delta.manhattanLength() < threshold:
                    return

                # 超過門檻才真正開始框選
                self.tile_selection_mode = True
                self._drag_selecting = True

            self._drag_end_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = False
            return

        if self.tile_grid_mode and event.button() == Qt.MouseButton.LeftButton:

            mx, my = event.position().x(), event.position().y()

            # ===== 拖曳框選完成 =====
            if self._drag_selecting:
                select_tiles_in_rect(self._drag_start_pos, self._drag_end_pos, self)
                self._drag_selecting = False
                self._drag_start_pos = None
                self._drag_end_pos = None
                self.update()
                return

            # ===== 單擊圖片切換選取 =====
            clicked_tile = None
            for x0, y0, x1, y1, path in self.tile_rects:
                if x0 <= mx <= x1 and y0 <= my <= y1:
                    clicked_tile = path
                    break

            if clicked_tile:

                if not self.tile_selection_mode:
                    # 正常模式 → 進入 DeepZoom
                    self._saved_tile_state = {
                        "grid_offset_x": self.grid_offset_x,
                        "grid_offset_y": self.grid_offset_y,
                        "tile_scale": self.tile_scale,
                    }
                    self.tile_grid_mode = False
                    if clicked_tile in self.model.images:
                        self.current_index = self.model.images.index(clicked_tile)
                    self.load_deep_zoom_image(clicked_tile)
                    return

                # 已在選取模式 → 才做多選
                if clicked_tile in self.selected_tiles:
                    self.selected_tiles.remove(clicked_tile)
                else:
                    self.selected_tiles.add(clicked_tile)

                self.update()
                return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        from Imervue.gui.shortcut_settings_dialog import shortcut_manager

        key = event.key()
        modifiers = event.modifiers()

        # Plugin hook: key press
        if (
            hasattr(self.main_window, "plugin_manager")
            and self.main_window.plugin_manager.dispatch_key_press(key, modifiers, self)
        ):
            return

        shift = modifiers & Qt.KeyboardModifier.ShiftModifier

        # ===== F8 — OSD / Debug HUD =====
        # Moved from F3 to free up F1-F5 for colour labels (Lightroom-style).
        if key == Qt.Key.Key_F8:
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self._show_debug_hud = not self._show_debug_hud
            else:
                self._show_osd = not self._show_osd
            self.update()
            return

        # ===== F1-F5 — colour labels (red/yellow/green/blue/purple) =====
        # Toggles: pressing the same F-key again clears the flag.
        _COLOR_KEYS = {
            Qt.Key.Key_F1: "red",
            Qt.Key.Key_F2: "yellow",
            Qt.Key.Key_F3: "green",
            Qt.Key.Key_F4: "blue",
            Qt.Key.Key_F5: "purple",
        }
        if key in _COLOR_KEYS and not (modifiers & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier)):
            self._apply_color_label(_COLOR_KEYS[key])
            return

        # ===== Escape — always hardcoded (not remappable) =====
        if key == Qt.Key.Key_Escape:
            if hasattr(self, '_slideshow') and self._slideshow and self._slideshow.running:
                stop_slideshow(self)
                return
            if self.main_window.isFullScreen():
                toggle_fullscreen(self)
                return
            if self.tile_grid_mode and self.selected_tiles:
                self.tile_selection_mode = False
                self.selected_tiles.clear()
                self.update()
                return
            if self.deep_zoom or self.active_deep_zoom_worker:
                self._cancel_deep_zoom_worker()
                self._cancel_all_prefetch()
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
                return

        # ===== Arrow keys — always hardcoded (not remappable) =====
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
            # Ctrl+Shift+←/→ → 跨資料夾導航（無論 deep zoom 或 tile grid）
            if ctrl and shift and key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                if key == Qt.Key.Key_Right:
                    switch_to_next_folder(main_gui=self)
                else:
                    switch_to_previous_folder(main_gui=self)
                return

            step = self.thumbnail_size or 1024
            fine_step = int(step / 2)
            move_step = fine_step if shift else step
            if self.tile_grid_mode:
                if key == Qt.Key.Key_Up:
                    self.grid_offset_y += move_step
                elif key == Qt.Key.Key_Down:
                    self.grid_offset_y -= move_step
                elif key == Qt.Key.Key_Left:
                    self.grid_offset_x += move_step
                elif key == Qt.Key.Key_Right:
                    self.grid_offset_x -= move_step
                self.update()
                return
            if self.deep_zoom:
                if key == Qt.Key.Key_Right:
                    switch_to_next_image(main_gui=self)
                    return
                elif key == Qt.Key.Key_Left:
                    switch_to_previous_image(main_gui=self)
                    return

        # ===== Remappable shortcuts via ShortcutManager =====
        mods_int = modifiers.value if hasattr(modifiers, "value") else int(modifiers)
        action = shortcut_manager.get_action(key, mods_int)
        if action is None:
            return

        # --- Undo / Redo ---
        if action == "undo":
            if self.undo_manager.canUndo():
                self.undo_manager.undo()
            else:
                undo_delete(main_gui=self)
            return
        if action in ("redo", "redo_alt"):
            self.undo_manager.redo()
            return

        # --- Clipboard ---
        if action == "copy":
            copy_image_to_clipboard(self)
            return
        if action == "paste":
            self._paste_image_from_clipboard()
            return

        # --- Search ---
        if action in ("search", "search_alt"):
            open_search_dialog(self)
            return

        # --- Go to index (Ctrl+G) ---
        if action == "goto":
            open_goto_dialog(self)
            return

        # --- Fullscreen ---
        if action == "fullscreen":
            toggle_fullscreen(self)
            return

        # --- Theater mode (Shift+Tab) ---
        if action == "theater":
            if hasattr(self.main_window, "toggle_theater_mode"):
                self.main_window.toggle_theater_mode()
            return

        # --- Pixel view (Shift+P) ---
        if action == "pixel_view":
            if self.deep_zoom:
                self._pixel_view = not self._pixel_view
                if self._pixel_view and hasattr(self.main_window, "toast"):
                    lang = self.main_window.language_wrapper.language_word_dict
                    self.main_window.toast.info(
                        lang.get("pixel_view_hint",
                                 "Pixel view — zoom in to ≥400% to see grid")
                    )
                self.update()
            return

        # --- History navigation (Alt+←/→) ---
        if action == "history_back":
            if not self.history_back():
                lang = self.main_window.language_wrapper.language_word_dict
                if hasattr(self.main_window, "toast"):
                    self.main_window.toast.info(
                        lang.get("history_at_start", "At start of history")
                    )
            return
        if action == "history_forward":
            if not self.history_forward():
                lang = self.main_window.language_wrapper.language_word_dict
                if hasattr(self.main_window, "toast"):
                    self.main_window.toast.info(
                        lang.get("history_at_end", "At end of history")
                    )
            return

        # --- Random image (X) ---
        if action == "random_image":
            self.jump_to_random_image()
            return

        # --- Split view (Shift+S) ---
        if action == "split_view":
            if hasattr(self.main_window, "activate_dual_view"):
                self.main_window.activate_dual_view("split")
            return

        # --- Dual page manga (Shift+D) ---
        if action == "dual_page":
            if hasattr(self.main_window, "activate_dual_view"):
                # Toggle between LTR and RTL with Ctrl
                mode = "manga_rtl" if modifiers & Qt.KeyboardModifier.ControlModifier else "manga"
                self.main_window.activate_dual_view(mode)
            return

        # --- Multi-monitor window (Ctrl+Shift+M) ---
        if action == "multi_monitor":
            if hasattr(self.main_window, "toggle_multi_monitor_window"):
                self.main_window.toggle_multi_monitor_window()
            return

        # --- Color mode cycle (Shift+M) ---
        if action == "color_mode_cycle":
            self.renderer.color_mode = (self.renderer.color_mode + 1) % 4
            names = ["Normal", "Grayscale", "Invert", "Sepia"]
            keys = ["color_mode_normal", "color_mode_grayscale",
                    "color_mode_invert", "color_mode_sepia"]
            if hasattr(self.main_window, "toast"):
                lang = self.main_window.language_wrapper.language_word_dict
                label = lang.get(keys[self.renderer.color_mode],
                                 names[self.renderer.color_mode])
                self.main_window.toast.info(label)
            self.update()
            return

        # --- Edit / Annotate ---
        if action == "edit":
            if self.deep_zoom:
                images = self.model.images
                if images and 0 <= self.current_index < len(images):
                    open_annotation_for_path(self, images[self.current_index])
            return

        # --- Slideshow ---
        if action == "slideshow":
            open_slideshow_dialog(self)
            return

        # --- Tags & Albums ---
        if action == "tags":
            from Imervue.gui.tag_album_dialog import open_tag_album_dialog
            open_tag_album_dialog(self)
            return

        # --- Histogram ---
        if action == "histogram":
            if self.deep_zoom:
                self._show_histogram = not self._show_histogram
                self.update()
            return

        # --- Fit width / height ---
        if action == "fit_width":
            if self.deep_zoom:
                self._fit_to_width()
                lang = self.main_window.language_wrapper.language_word_dict
                if hasattr(self.main_window, 'toast'):
                    self.main_window.toast.info(lang.get("fit_width", "Fit Width"))
            return
        if action == "fit_height":
            if self.deep_zoom:
                self._fit_to_height()
                lang = self.main_window.language_wrapper.language_word_dict
                if hasattr(self.main_window, 'toast'):
                    self.main_window.toast.info(lang.get("fit_height", "Fit Height"))
            return

        # --- Bookmark ---
        if action == "bookmark":
            if self.deep_zoom:
                self._toggle_bookmark()
            return

        # --- Rotate ---
        if action == "rotate_cw":
            if self.deep_zoom:
                from Imervue.gpu_image_view.actions.undo_commands import RotateCommand
                self.undo_manager.push(RotateCommand(self, clockwise=True))
            return
        if action == "rotate_ccw":
            if self.deep_zoom:
                from Imervue.gpu_image_view.actions.undo_commands import RotateCommand
                self.undo_manager.push(RotateCommand(self, clockwise=False))
            return

        # --- Reset view ---
        if action == "reset_view":
            if self.deep_zoom:
                self.zoom = 1.0
                self.dz_offset_x = 0
                self.dz_offset_y = 0
            elif self.tile_grid_mode:
                self.grid_offset_x = 0
                self.grid_offset_y = 0
            self.update()
            return

        # --- Favorite ---
        if action == "favorite":
            toggle_favorite(self)
            return

        # --- Quick rating 1-5 ---
        if action in ("rate_1", "rate_2", "rate_3", "rate_4", "rate_5"):
            rating = int(action[-1])
            rate_current_image(self, rating)
            return

        # --- Delete ---
        if action == "delete":
            if self.tile_grid_mode and self.tile_selection_mode:
                trash_selected_tiles(self)
            elif self.deep_zoom:
                trash_current_image(self)
            return

        # --- Animation controls ---
        if self._animation and self._animation.is_animated:
            if action == "anim_toggle":
                self._animation.toggle()
                return
            if action == "anim_prev":
                self._animation.prev_frame()
                return
            if action == "anim_next":
                self._animation.next_frame()
                return
            if action == "anim_slower":
                self._animation.set_speed(self._animation.speed / 1.5)
                if hasattr(self.main_window, 'toast'):
                    self.main_window.toast.info(f"Speed: {self._animation.speed:.2f}x")
                return
            if action == "anim_faster":
                self._animation.set_speed(self._animation.speed * 1.5)
                if hasattr(self.main_window, 'toast'):
                    self.main_window.toast.info(f"Speed: {self._animation.speed:.2f}x")
                return

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
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

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
