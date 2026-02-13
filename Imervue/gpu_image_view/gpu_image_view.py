from __future__ import annotations

import os
from typing import TYPE_CHECKING

from Imervue.gpu_image_view.actions.delete import delete_current_image, delete_selected_tiles, undo_delete
from Imervue.gpu_image_view.actions.select import switch_to_next_image, switch_to_previous_image
from Imervue.gpu_image_view.images.image_loader import load_image_file
from Imervue.gpu_image_view.images.image_model import ImageModel

if TYPE_CHECKING:
    from Imervue.main_window import ImervueMainWindow

import numpy as np
from OpenGL.GL import *
from PySide6.QtCore import QThreadPool, QMutex, QTimer, QRectF, Qt
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from Imervue.image_type.load_thumbnail_worker import LoadThumbnailWorker
from Imervue.image_type.pyramid import DeepZoomImage
from Imervue.image_type.tile_manager import TileManager


class GPUImageView(QOpenGLWidget):
    def __init__(self, main_window: ImervueMainWindow):
        super().__init__()

        self.main_window = main_window

        # ===== 模式 =====
        self.tile_grid_mode = False
        self.deep_zoom_mode = False
        self.selected_image_path = None

        # ===== Undo =====
        self.deleted_stack = []
        self.undo_stack = []

        # ===== Tile Grid =====

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

        # ===== offset =====
        self.offset_x = None
        self.offset_y = None

        # ===== 圖片切換控制 =====
        self.model = ImageModel()
        self.model.images = []  # 所有圖片路徑
        self.current_index = 0
        self.switch_threshold = 120  # 水平拖動超過多少 px 切換
        self.drag_accumulator = 0
        self.on_filename_changed = None
        self.deep_zoom_tile_size = 512
        self.thumbnail_size = 256

        # ===== Tile Grid 選取模式 =====
        self.tile_selection_mode = False  # 是否在選取模式
        self.selected_tiles = set()  # 已選取的 tile path
        self.long_press_threshold = 500  # 長按進入選取模式的毫秒
        self._press_timer = None
        self._drag_selecting = False  # 是否正在拖曳框選
        self._drag_start_pos = None
        self._drag_end_pos = None

        # ===== Mouse =====
        self._middle_dragging = None
        self._press_pos = None

        # ===== Thread =====
        self.thread_pool = QThreadPool.globalInstance()
        self.grid_mutex = QMutex()  # 保護 tile_grid 併發更新
        self.active_tile_workers = []  # 用來追蹤 Tile Grid 載入 worker
        self.active_deep_zoom_worker = None

        # ===== Focus ======
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    # ===========================
    # OpenGL 初始化
    # ===========================
    def initializeGL(self):
        glEnable(GL_TEXTURE_2D)
        glClearColor(0.1, 0.1, 0.1, 1)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, w, h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)

    # ===========================
    # 繪製
    # ===========================
    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT)

        # ===== Tile Grid Mode =====
        if self.tile_grid_mode:
            self.paint_tile_grid()
        # ===== DeepZoom Mode =====
        elif self.deep_zoom:
            self.paint_deep_zoom()

    # ---------------------------
    # Tile Grid Lazy Render
    # ---------------------------
    def paint_tile_grid(self):

        glLoadIdentity()

        images = self.model.images
        scaled_tile = self.thumbnail_size * self.tile_scale
        cols = max(1, int(self.width() // scaled_tile))

        self.tile_rects = []

        for i, path in enumerate(images):

            # 🔥 沒載入完成就跳過
            if path not in self.tile_cache:
                continue

            img_data = self.tile_cache[path]

            row = i // cols
            col = i % cols

            x0 = col * scaled_tile + self.grid_offset_x
            y0 = row * scaled_tile + self.grid_offset_y
            x1 = x0 + img_data.shape[1] * self.tile_scale
            y1 = y0 + img_data.shape[0] * self.tile_scale

            # Viewport 裁切
            if x1 < 0 or x0 > self.width() or y1 < 0 or y0 > self.height():
                continue

            self.tile_rects.append((x0, y0, x1, y1, path))

            # ===== GPU texture =====
            if path not in self.tile_textures:
                tex = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, tex)
                glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                             img_data.shape[1], img_data.shape[0], 0,
                             GL_RGBA, GL_UNSIGNED_BYTE, img_data)

                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

                self.tile_textures[path] = tex

            glColor4f(1, 1, 1, 1)
            glBindTexture(GL_TEXTURE_2D, self.tile_textures[path])

            glBegin(GL_QUADS)
            glTexCoord2f(0, 1)
            glVertex2f(x0, y1)
            glTexCoord2f(1, 1)
            glVertex2f(x1, y1)
            glTexCoord2f(1, 0)
            glVertex2f(x1, y0)
            glTexCoord2f(0, 0)
            glVertex2f(x0, y0)
            glEnd()

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

        level, _ = self.deep_zoom.get_level(self.zoom)
        level_image = self.deep_zoom.levels[level]
        base_image = self.deep_zoom.levels[0]
        scale_x = self.zoom * (level_image.shape[1] / base_image.shape[1])
        scale_y = self.zoom * (level_image.shape[0] / base_image.shape[0])

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
                        self.tile_manager.load_tile_async(level, tx, ty, tile_size)
                        continue
                    glBindTexture(GL_TEXTURE_2D, tex)
                    tile_w = min(tile_size, w - tx * tile_size)
                    tile_h = min(tile_size, h - ty * tile_size)
                    x = tx * tile_size
                    y = ty * tile_size
                    glBegin(GL_QUADS)
                    glTexCoord2f(0, 1)
                    glVertex2f(x, y + tile_h)
                    glTexCoord2f(1, 1)
                    glVertex2f(x + tile_w, y + tile_h)
                    glTexCoord2f(1, 0)
                    glVertex2f(x + tile_w, y)
                    glTexCoord2f(0, 0)
                    glVertex2f(x, y)
                    glEnd()

    # ===========================
    # 非同步載入縮圖
    # ===========================
    def load_tile_grid_async(self, image_paths):

        self.model.set_images(image_paths)

        self.tile_cache.clear()
        self.tile_textures.clear()

        self.tile_grid_mode = True
        self.deep_zoom = None

        for path in image_paths:
            worker = LoadThumbnailWorker(path, self.thumbnail_size)
            worker.signals.finished.connect(self.add_thumbnail)
            self.thread_pool.start(worker)

        self.update()

    def load_deep_zoom_image(self, path):
        img_data = load_image_file(path, thumbnail=False)
        self.deep_zoom = DeepZoomImage(img_data)
        self.tile_manager = TileManager(self.deep_zoom)

        self.zoom = 1.0
        self.dz_offset_x = 0
        self.dz_offset_y = 0

        self.update()

        if self.on_filename_changed:
            self.on_filename_changed(os.path.basename(path))

    def clear_tile_grid(self):
        self.tile_grid_mode = False
        self.tile_rects = []

        # 重置偏移量
        self.grid_offset_x = 0
        self.grid_offset_y = 0

        self.update()

    def add_thumbnail(self, img_data, path):

        # 如果已被刪除，不加入
        if path not in self.model.images:
            return

        self.tile_cache[path] = img_data
        self.update()

    # ===========================
    # Event
    # ===========================
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9

        if self.tile_grid_mode:
            self.tile_scale *= factor
            self.tile_scale = max(0.1, min(5.0, self.tile_scale))
            self.update()

        elif self.deep_zoom:
            old_zoom = self.zoom
            self.zoom *= factor

            cx, cy = self.width() / 2, self.height() / 2

            self.dz_offset_x = cx - (cx - self.dz_offset_x) * (self.zoom / old_zoom)
            self.dz_offset_y = cy - (cy - self.dz_offset_y) * (self.zoom / old_zoom)

            self.update()

    def mousePressEvent(self, event):
        self.last_pos = event.position()
        self.drag_accumulator = 0
        # ===== 中鍵 → 進入拖動模式 =====
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = True
            return

        # ===== 左鍵 → 原本邏輯 =====
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.tile_grid_mode:
                self._press_pos = event.position()

                self._press_timer = QTimer(self)
                self._press_timer.setSingleShot(True)
                self._press_timer.timeout.connect(self.start_tile_selection)
                self._press_timer.start(self.long_press_threshold)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
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

        # ===== 左鍵框選 =====
        if self.tile_grid_mode and self._drag_selecting:
            self._drag_end_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = False
            return

        if self._press_timer:
            self._press_timer.stop()
            self._press_timer = None

        self._press_pos = None

        if self.tile_grid_mode:
            mx, my = event.position().x(), event.position().y()

            if self._drag_selecting:
                # 拖曳框選完成
                self.select_tiles_in_rect(self._drag_start_pos, self._drag_end_pos)
                self._drag_selecting = False
                self._drag_start_pos = None
                self._drag_end_pos = None
                self.update()
                return

            clicked_any_tile = False

            # 單點選擇
            for x0, y0, x1, y1, path in self.tile_rects:
                if x0 <= mx <= x1 and y0 <= my <= y1:
                    if self.tile_selection_mode:
                        if path in self.selected_tiles:
                            self.selected_tiles.remove(path)
                        else:
                            self.selected_tiles.add(path)
                        self.update()
                        return
                    else:
                        self.current_index = self.model.images.index(path)
                        self.tile_grid_mode = False
                        self.load_deep_zoom_image(path)
                        self.update()
                        return
            # 如果在選取模式，且點擊空白 → 退出選取模式
            if self.tile_selection_mode and not clicked_any_tile:
                self.tile_selection_mode = False
                self.selected_tiles.clear()
                self.update()

    def start_tile_selection(self):
        if not self._press_pos:
            return

        self.tile_selection_mode = True
        self._drag_selecting = True

        self._drag_start_pos = self._press_pos
        self._drag_end_pos = self._press_pos

        self.update()

    def select_tiles_in_rect(self, start_pos, end_pos):
        if start_pos is None or end_pos is None:
            return

        x0, y0 = start_pos.x(), start_pos.y()
        x1, y1 = end_pos.x(), end_pos.y()
        rect = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

        for tx0, ty0, tx1, ty1, path in self.tile_rects:
            tile_rect = QRectF(tx0, ty0, tx1 - tx0, ty1 - ty0)
            if rect.intersects(tile_rect):
                self.selected_tiles.add(path)

    def keyPressEvent(self, event):
        key = event.key()
        # Undo
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Z:
                undo_delete(main_gui=self)
                return

        # Tile Grid 刪除
        if self.tile_grid_mode and self.tile_selection_mode:
            if key == Qt.Key.Key_Delete:
                delete_selected_tiles(main_gui=self)
                return

        # DeepZoom
        if self.deep_zoom:
            if key == Qt.Key.Key_Right:
                switch_to_next_image(main_gui=self)
                return
            elif key == Qt.Key.Key_Left:
                switch_to_previous_image(main_gui=self)
                return
            elif key == Qt.Key.Key_Delete:
                delete_current_image(main_gui=self)
                return
